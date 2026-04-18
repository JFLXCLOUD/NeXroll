import React, { useState, useEffect, useCallback } from 'react';
// eslint-disable-next-line no-unused-vars
import SequenceTimeline from './SequenceTimeline';
// eslint-disable-next-line no-unused-vars
import SequenceStats from './SequenceStats';

/**
 * SequencePreviewModal - Full-screen preview modal with playback simulator
 * Shows timeline visualization, statistics, and simulates sequence playback
 * 
 * Props:
 * - isOpen: Boolean - whether modal is visible
 * - onClose: Function - callback to close modal
 * - blocks: Array of sequence blocks
 * - categories: Array of available categories
 * - prerolls: Array of all prerolls
 * - sequenceName: String - name of the sequence
 * - apiUrl: Function - API URL builder
 */
const SequencePreviewModal = ({ isOpen, onClose, blocks = [], categories = [], prerolls = [], sequenceName = 'Untitled Sequence', apiUrl }) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentBlockIndex, setCurrentBlockIndex] = useState(-1);
  const [currentPrerollIndex, setCurrentPrerollIndex] = useState(0);
  const [playbackProgress, setPlaybackProgress] = useState(0);
  const [expandedBlocks, setExpandedBlocks] = useState(new Set());
  const [playlist, setPlaylist] = useState([]);
  const videoRef = React.useRef(null);
  const isTransitioningRef = React.useRef(false);
  const expectedIndexRef = React.useRef(0);
  // Snapshot props at modal-open time so background refetches don't rebuild the playlist
  const snapshotRef = React.useRef({ prerolls: [], categories: [], blocks: [] });
  const [modalOpenCounter, setModalOpenCounter] = useState(0);

  // Get preroll details for a block (uses snapshot to avoid mid-playback changes)
  const getBlockPrerolls = useCallback((block, snapshotPrerolls) => {
    const prs = snapshotPrerolls;
    if (block.type === 'preroll') {
      const preroll = prs.find((p) => p.id === block.preroll_id);
      return preroll ? [preroll] : [];
    } else if (block.type === 'fixed') {
      // Fixed block with specific preroll IDs
      if (!block.preroll_ids || block.preroll_ids.length === 0) return [];
      return block.preroll_ids
        .map(id => prs.find(p => p.id === id))
        .filter(Boolean);
    } else if (block.type === 'random' || block.type === 'sequential') {
      // Filter to only prerolls with existing files for random/sequential selection
      return prs.filter((p) => p.category_id === block.category_id && p.file_exists !== false);
    } else if (block.type === 'queue') {
      return []; // Queue items would be dynamic
    } else if (block.type === 'sequence') {
      return []; // Nested sequence
    }
    return [];
  }, []);

  // Snapshot props when modal opens, increment counter to trigger playlist build once
  useEffect(() => {
    if (isOpen) {
      snapshotRef.current = { prerolls: [...prerolls], categories: [...categories], blocks: [...blocks] };
      setModalOpenCounter(c => c + 1);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  // Build the playlist ONCE when the modal opens (keyed off modalOpenCounter)
  useEffect(() => {
    if (!isOpen) {
      setIsPlaying(false);
      setCurrentBlockIndex(-1);
      setCurrentPrerollIndex(0);
      setPlaybackProgress(0);
      setPlaylist([]);
      return;
    }

    const snap = snapshotRef.current;

    // Build playlist from blocks
    const newPlaylist = [];
    snap.blocks.forEach((block, blockIndex) => {
      const blockPrerolls = getBlockPrerolls(block, snap.prerolls);
      
      if (block.type === 'random' && blockPrerolls.length > 0) {
        // Pick count random prerolls from the category (shuffle + slice)
        const count = Math.max(1, Math.min(block.count || 1, blockPrerolls.length));
        const shuffled = [...blockPrerolls].sort(() => Math.random() - 0.5);
        shuffled.slice(0, count).forEach(preroll => {
          newPlaylist.push({ blockIndex, preroll, blockType: 'random' });
        });
      } else if (block.type === 'sequential' && blockPrerolls.length > 0) {
        // Pick the first preroll from the category (simulating sequential)
        newPlaylist.push({ blockIndex, preroll: blockPrerolls[0], blockType: 'sequential' });
      } else if (block.type === 'preroll') {
        const preroll = snap.prerolls.find(p => p.id === block.preroll_id);
        if (preroll) {
          newPlaylist.push({ blockIndex, preroll, blockType: 'preroll' });
        }
      } else if (block.type === 'fixed' && block.preroll_ids) {
        // Add all fixed prerolls in order
        block.preroll_ids.forEach(prerollId => {
          const preroll = snap.prerolls.find(p => p.id === prerollId);
          if (preroll) {
            newPlaylist.push({ blockIndex, preroll, blockType: 'fixed' });
          }
        });
      }
    });

    setPlaylist(newPlaylist);
  }, [isOpen, modalOpenCounter, getBlockPrerolls]);

  // Start playback
  const startPlayback = () => {
    if (playlist.length === 0) return;
    isTransitioningRef.current = false;
    expectedIndexRef.current = 0;
    setIsPlaying(true);
    setCurrentPrerollIndex(0);
    setCurrentBlockIndex(playlist[0].blockIndex);
    setPlaybackProgress(0);
  };

  // Stop playback
  const stopPlayback = () => {
    isTransitioningRef.current = false;
    setIsPlaying(false);
    setCurrentBlockIndex(-1);
    setCurrentPrerollIndex(0);
    setPlaybackProgress(0);
    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.currentTime = 0;
    }
  };

  // Helper function to get video URL for a preroll
  const getVideoUrl = (preroll) => {
    if (!preroll || !apiUrl) {
      return '';
    }
    
    // Get category name from preroll's category object or find it in snapshot categories
    let categoryName = 'unknown';
    if (preroll.category && preroll.category.name) {
      categoryName = preroll.category.name;
    } else if (preroll.category_id) {
      const category = snapshotRef.current.categories.find(c => c.id === preroll.category_id);
      if (category) {
        categoryName = category.name;
      }
    }
    
    // Build the URL using the same format as regular preview
    return apiUrl(`static/prerolls/${encodeURIComponent(categoryName)}/${encodeURIComponent(preroll.filename)}`);
  };

  // Handle video ended - move to next preroll
  const handleVideoEnded = () => {
    // Ignore if we're in the middle of a source transition
    if (isTransitioningRef.current) return;
    const nextIndex = currentPrerollIndex + 1;
    if (nextIndex < playlist.length) {
      expectedIndexRef.current = nextIndex;
      setCurrentPrerollIndex(nextIndex);
      setCurrentBlockIndex(playlist[nextIndex].blockIndex);
      setPlaybackProgress((nextIndex / playlist.length) * 100);
    } else {
      // Playback complete
      setIsPlaying(false);
      setCurrentBlockIndex(-1);
      setPlaybackProgress(100);
    }
  };

  // Handle video error - skip to next preroll (e.g. 404 / missing file)
  const handleVideoError = () => {
    // Ignore abort errors that fire during normal source transitions
    const error = videoRef.current?.error;
    if (!error || error.code === 1 /* MEDIA_ERR_ABORTED */) return;
    // Also ignore errors during active source transitions
    if (isTransitioningRef.current) return;
    const nextIndex = currentPrerollIndex + 1;
    if (nextIndex < playlist.length) {
      expectedIndexRef.current = nextIndex;
      setCurrentPrerollIndex(nextIndex);
      setCurrentBlockIndex(playlist[nextIndex].blockIndex);
      setPlaybackProgress((nextIndex / playlist.length) * 100);
    } else {
      setIsPlaying(false);
      setCurrentBlockIndex(-1);
      setPlaybackProgress(100);
    }
  };

  // Handle canplay - source has loaded successfully, transition complete
  const handleCanPlay = () => {
    isTransitioningRef.current = false;
  };

  // When track index changes, load the new src into the same video element
  useEffect(() => {
    if (!isPlaying || !videoRef.current || playlist.length === 0) return;
    const item = playlist[currentPrerollIndex];
    if (!item) return;
    const url = getVideoUrl(item.preroll);
    if (url) {
      isTransitioningRef.current = true;
      videoRef.current.src = url;
      videoRef.current.load();
      videoRef.current.play().catch(() => {});
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentPrerollIndex, isPlaying]);

  // Handle video time update
  const handleTimeUpdate = () => {
    if (videoRef.current && playlist.length > 0) {
      const currentProgress = (currentPrerollIndex / playlist.length) * 100;
      const videoProgress = (videoRef.current.currentTime / videoRef.current.duration) * (100 / playlist.length);
      setPlaybackProgress(currentProgress + videoProgress);
    }
  };

  // eslint-disable-next-line no-unused-vars
  const toggleBlockExpanded = (index) => {
    const newExpanded = new Set(expandedBlocks);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedBlocks(newExpanded);
  };

  // Get category name
  // eslint-disable-next-line no-unused-vars
  const getCategoryName = (categoryId) => {
    const category = categories.find((c) => c.id === categoryId);
    return category?.name || 'Unknown Category';
  };

  // Get block icon
  // eslint-disable-next-line no-unused-vars
  const getBlockIcon = (type) => {
    const icons = {
      preroll: '🎬',
      fixed: '📌',
      random: '🎲',
      sequential: '📋',
      queue: '⏭️',
      sequence: '🔗',
      separator: '┃',
    };
    return icons[type] || '❓';
  };

  // Get block color
  // eslint-disable-next-line no-unused-vars
  const getBlockColor = (type) => {
    const colors = {
      preroll: '#667eea',
      fixed: '#dc2626',
      random: '#f59e0b',
      sequential: '#10b981',
      queue: '#ec4899',
      sequence: '#8b5cf6',
      separator: '#6b7280',
    };
    return colors[type] || '#9ca3af';
  };

  // Format duration
  // eslint-disable-next-line no-unused-vars
  const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.85)',
        zIndex: 10000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '2rem',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      {/* Compact Video Player Overlay */}
      <div
        style={{
          backgroundColor: 'var(--card-bg)',
          borderRadius: '12px',
          overflow: 'hidden',
          maxWidth: '90vw',
          maxHeight: '90vh',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Compact Header */}
        <div
          style={{
            padding: '1rem 1.5rem',
            borderBottom: '1px solid var(--border-color)',
            backgroundColor: 'var(--bg-color)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '1.5rem' }}>🎬</span>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--text-color)' }}>
                {sequenceName}
              </h3>
              <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                {playlist.length} preroll{playlist.length !== 1 ? 's' : ''} • {blocks.length} block{blocks.length !== 1 ? 's' : ''}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              width: '32px',
              height: '32px',
              padding: 0,
              backgroundColor: 'transparent',
              color: 'var(--text-secondary)',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '1.25rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.2s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = 'var(--hover-bg)';
              e.currentTarget.style.color = 'var(--text-color)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'transparent';
              e.currentTarget.style.color = 'var(--text-secondary)';
            }}
            title="Close"
          >
            ✕
          </button>
        </div>

        {/* Video Player */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          {blocks.length === 0 ? (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '3rem 2rem',
                textAlign: 'center',
                minHeight: '400px',
              }}
            >
              <div style={{ fontSize: '4rem', marginBottom: '1rem', opacity: 0.5 }}>🎬</div>
              <h3 style={{ color: 'var(--text-color)', marginBottom: '0.5rem', margin: 0 }}>
                No Blocks in Sequence
              </h3>
              <p style={{ color: 'var(--text-secondary)', margin: '0.5rem 0 0 0' }}>
                Add blocks to your sequence to preview playback.
              </p>
            </div>
          ) : !isPlaying ? (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '3rem 2rem',
                textAlign: 'center',
                minHeight: '400px',
                backgroundColor: '#000',
              }}
            >
              <div style={{ fontSize: '4rem', marginBottom: '1rem' }}>▶️</div>
              <h3 style={{ color: '#fff', marginBottom: '1rem', margin: '0 0 1rem 0' }}>
                Ready to Play
              </h3>
              <p style={{ color: 'rgba(255, 255, 255, 0.7)', margin: '0 0 1.5rem 0', maxWidth: '400px' }}>
                Click the play button below to start the sequence preview. Random category blocks will select a random preroll.
              </p>
              <button
                onClick={startPlayback}
                disabled={playlist.length === 0}
                style={{
                  padding: '0.875rem 2rem',
                  backgroundColor: '#667eea',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  cursor: playlist.length === 0 ? 'not-allowed' : 'pointer',
                  fontSize: '1.05rem',
                  fontWeight: 600,
                  opacity: playlist.length === 0 ? 0.5 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  transition: 'all 0.2s',
                }}
                onMouseEnter={(e) => {
                  if (playlist.length > 0) {
                    e.currentTarget.style.backgroundColor = '#5568d3';
                    e.currentTarget.style.transform = 'translateY(-2px)';
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#667eea';
                  e.currentTarget.style.transform = 'translateY(0)';
                }}
              >
                ▶ Play Sequence
              </button>
            </div>
          ) : (
            <>
              <video
                ref={videoRef}
                autoPlay
                controls
                onEnded={handleVideoEnded}
                onError={handleVideoError}
                onCanPlay={handleCanPlay}
                onTimeUpdate={handleTimeUpdate}
                style={{
                  width: '100%',
                  height: 'auto',
                  maxHeight: '70vh',
                  backgroundColor: '#000',
                  display: 'block',
                }}
              />
              
              {/* Playback Progress Bar */}
              <div
                style={{
                  width: '100%',
                  height: '3px',
                  backgroundColor: 'rgba(102, 126, 234, 0.2)',
                }}
              >
                <div
                  style={{
                    width: `${playbackProgress}%`,
                    height: '100%',
                    backgroundColor: '#667eea',
                    transition: 'width 0.1s linear',
                  }}
                />
              </div>

              {/* Now Playing Info */}
              <div
                style={{
                  padding: '1rem 1.5rem',
                  backgroundColor: 'var(--bg-color)',
                  borderTop: '1px solid var(--border-color)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
                      Now Playing • Block {currentBlockIndex + 1}
                    </div>
                    <div 
                      style={{ 
                        fontSize: '0.95rem', 
                        fontWeight: 600, 
                        color: 'var(--text-color)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap'
                      }}
                      title={playlist[currentPrerollIndex]?.preroll?.display_name || playlist[currentPrerollIndex]?.preroll?.filename}
                    >
                      {playlist[currentPrerollIndex]?.preroll?.display_name || playlist[currentPrerollIndex]?.preroll?.filename}
                    </div>
                  </div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginLeft: '1rem', flexShrink: 0 }}>
                    {currentPrerollIndex + 1} / {playlist.length}
                  </div>
                </div>
                
                {/* Stop Button */}
                <button
                  onClick={stopPlayback}
                  style={{
                    width: '100%',
                    padding: '0.625rem',
                    backgroundColor: 'var(--bg-color)',
                    color: 'var(--text-color)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '0.9rem',
                    fontWeight: 600,
                    transition: 'all 0.2s',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = '#ef4444';
                    e.currentTarget.style.borderColor = '#ef4444';
                    e.currentTarget.style.color = 'white';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'var(--bg-color)';
                    e.currentTarget.style.borderColor = 'var(--border-color)';
                    e.currentTarget.style.color = 'var(--text-color)';
                  }}
                >
                  ⏹ Stop Playback
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default SequencePreviewModal;
