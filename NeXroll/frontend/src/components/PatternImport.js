import React, { useState, useEffect, useRef } from 'react';
import { Download, Check, CheckCircle, AlertTriangle, XCircle, Package, Folder, FileText, Lightbulb, Eye, ArrowLeft, Loader2, ClipboardList, Cloud, CloudDownload, RefreshCw, FolderOpen, ChevronDown, ChevronRight, Play, Pause, SkipForward, SkipBack, Film, X } from 'lucide-react';

/**
 * PatternImport - Import sequence from .nexseq JSON pattern file
 * Shows preview, match status, and validation warnings before creating schedule
 * Supports downloading missing prerolls from Community Prerolls
 * 
 * Props:
 * - isOpen: Boolean - whether modal is visible
 * - onClose: Function - callback to close modal
 * - onImport: Function - callback with imported sequence data
 */
const PatternImport = ({ isOpen, onClose, onImport }) => {
  const [selectedFile, setSelectedFile] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [previewData, setPreviewData] = useState(null);
  const [error, setError] = useState(null);
  const [step, setStep] = useState('select'); // 'select', 'preview', 'folder-mapping', 'downloading', 'ready'
  const [downloadProgress, setDownloadProgress] = useState({ current: 0, total: 0, currentName: '' });
  const [downloadedPrerolls, setDownloadedPrerolls] = useState([]);
  const [downloadErrors, setDownloadErrors] = useState([]);
  
  // Folder mapping state for ZIP bundle imports
  const [availableCategories, setAvailableCategories] = useState([]);
  const [folderMappings, setFolderMappings] = useState({}); // { sourcePath: targetCategoryId }
  const [bundleContents, setBundleContents] = useState(null); // { categories: [], fixed: [], sequence: [], preview_id: null }
  const [expandedSections, setExpandedSections] = useState({ categories: true, fixed: true });
  
  // Video preview state
  const [showPreviewPlayer, setShowPreviewPlayer] = useState(false);
  const [currentPreviewIndex, setCurrentPreviewIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [previewPlaylist, setPreviewPlaylist] = useState([]); // Flattened list of video paths
  const videoRef = useRef(null);

  // Reset state when modal closes
  useEffect(() => {
    if (!isOpen) {
      // Cleanup preview files when closing
      if (bundleContents?.preview_id) {
        fetch(`/sequences/preview/${bundleContents.preview_id}`, { method: 'DELETE' }).catch(() => {});
      }
      setSelectedFile(null);
      setPreviewData(null);
      setError(null);
      setStep('select');
      setDownloadProgress({ current: 0, total: 0, currentName: '' });
      setDownloadedPrerolls([]);
      setDownloadErrors([]);
      setFolderMappings({});
      setBundleContents(null);
      setExpandedSections({ categories: true, fixed: true });
      setShowPreviewPlayer(false);
      setCurrentPreviewIndex(0);
      setIsPlaying(false);
      setPreviewPlaylist([]);
    }
  }, [isOpen, bundleContents?.preview_id]);

  // Fetch available categories when modal opens
  useEffect(() => {
    if (isOpen) {
      fetch('/categories')
        .then(res => res.json())
        .then(data => setAvailableCategories(data || []))
        .catch(err => console.error('Failed to fetch categories:', err));
    }
  }, [isOpen]);

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (file) {
      if (!file.name.endsWith('.nexseq') && !file.name.endsWith('.json') && !file.name.endsWith('.zip') && !file.name.endsWith('.nexbundle')) {
        setError('Please select a .nexseq, .json, .zip, or .nexbundle file');
        return;
      }
      setSelectedFile(file);
      setError(null);
      setPreviewData(null);
      setStep('select');
    }
  };

  // Preview the pattern file WITHOUT downloading
  const handlePreview = async () => {
    if (!selectedFile) return;

    setIsLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      // Always preview without auto_download first to see what's available
      const response = await fetch('/sequences/import?auto_download=false', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Import failed');
      }

      const data = await response.json();
      
      // Check if this is a .nexbundle preview (needs user review before import)
      if (data.bundle_preview && data.type === 'nexbundle') {
        // Store the preview data for the bundle preview step
        setPreviewData(data);
        // Also set bundleContents so preview player works
        setBundleContents(data.bundle_preview);
        setStep('bundle-preview');
        setIsLoading(false);
        return;
      }
      
      // Check if this was a bundle import (multiple sequences imported directly) - legacy path
      if (data.bundle_import && data.success) {
        // Bundle was imported successfully - notify and close
        if (onImport) {
          onImport(data);
        }
        setIsLoading(false);
        onClose();
        return;
      }
      
      setPreviewData(data);
      
      // For ZIP bundles, check if we have bundle contents to map
      if (selectedFile.name.endsWith('.zip') && data.bundle_preview) {
        // Setup folder mappings with defaults (same name as source)
        const defaultMappings = {};
        
        // Map category folders
        if (data.bundle_preview.categories) {
          data.bundle_preview.categories.forEach(cat => {
            // Try to find matching category by name, otherwise use 'new:' prefix for creating new
            const existingCat = availableCategories.find(c => 
              c.name.toLowerCase() === cat.name.toLowerCase()
            );
            defaultMappings[`category:${cat.name}`] = existingCat ? existingCat.id : `new:${cat.name}`;
          });
        }
        
        // Map fixed prerolls (each goes to a category)
        if (data.bundle_preview.fixed) {
          data.bundle_preview.fixed.forEach(preroll => {
            // Default to 'Imported' category or first available
            const importedCat = availableCategories.find(c => c.name === 'Imported');
            const defaultCat = availableCategories.find(c => c.name === 'Default');
            defaultMappings[`fixed:${preroll.name}`] = importedCat?.id || defaultCat?.id || (availableCategories[0]?.id || 'new:Imported');
          });
        }
        
        setBundleContents(data.bundle_preview);
        setFolderMappings(defaultMappings);
        setStep('folder-mapping');
      } else {
        setStep('preview');
      }
    } catch (err) {
      console.error('Import preview error:', err);
      setError(err.message || 'Failed to preview pattern');
    } finally {
      setIsLoading(false);
    }
  };

  // Handle folder mapping change
  const handleMappingChange = (sourceKey, targetValue) => {
    setFolderMappings(prev => ({
      ...prev,
      [sourceKey]: targetValue
    }));
  };

  // Build sequence preview playlist from bundle contents
  const buildPreviewPlaylist = () => {
    if (!bundleContents?.preview_id || !bundleContents?.sequence) return [];
    
    const playlist = [];
    const previewId = bundleContents.preview_id;
    
    // Go through sequence and build playlist
    bundleContents.sequence.forEach(item => {
      if (item.type === 'fixed' && item.path) {
        // Fixed block with a specific path
        playlist.push({
          name: item.name,
          url: `/sequences/preview-video/${previewId}/${encodeURIComponent(item.path)}`,
          type: 'fixed',
          category: item.category || null
        });
      } else if (item.type === 'random' && item.available_files && item.available_files.length > 0) {
        // Random block - pick 'count' random files to simulate actual playback
        const count = item.count || 1;
        const availableFiles = [...item.available_files]; // Copy array
        const selectedFiles = [];
        
        // Randomly select 'count' files (or all if count > available)
        for (let i = 0; i < Math.min(count, availableFiles.length); i++) {
          const randomIndex = Math.floor(Math.random() * availableFiles.length);
          selectedFiles.push(availableFiles[randomIndex]);
          availableFiles.splice(randomIndex, 1); // Remove to avoid duplicates
        }
        
        selectedFiles.forEach((filePath) => {
          const fileName = filePath.split('/').pop();
          const nameWithoutExt = fileName.replace(/\.[^.]+$/, '');
          playlist.push({
            name: nameWithoutExt,
            url: `/sequences/preview-video/${previewId}/${encodeURIComponent(filePath)}`,
            type: 'random',
            category: item.category,
            totalInCategory: item.available_files.length,
            countRequested: count
          });
        });
      }
    });
    
    return playlist;
  };

  // Start sequence preview
  const handleStartPreview = () => {
    const playlist = buildPreviewPlaylist();
    if (playlist.length > 0) {
      setPreviewPlaylist(playlist);
      setCurrentPreviewIndex(0);
      setShowPreviewPlayer(true);
      setIsPlaying(true);
    }
  };

  // Handle video ended - play next in sequence
  const handleVideoEnded = () => {
    if (currentPreviewIndex < previewPlaylist.length - 1) {
      setCurrentPreviewIndex(prev => prev + 1);
    } else {
      // Loop back to start
      setCurrentPreviewIndex(0);
    }
  };

  // Toggle play/pause
  const togglePlayPause = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  // Skip to next video
  const handleNextVideo = () => {
    if (currentPreviewIndex < previewPlaylist.length - 1) {
      setCurrentPreviewIndex(prev => prev + 1);
    }
  };

  // Skip to previous video
  const handlePrevVideo = () => {
    if (currentPreviewIndex > 0) {
      setCurrentPreviewIndex(prev => prev - 1);
    }
  };

  // Close preview player
  const handleClosePreview = () => {
    setShowPreviewPlayer(false);
    setIsPlaying(false);
    if (videoRef.current) {
      videoRef.current.pause();
    }
  };

  // Confirm folder mappings and proceed with import
  const handleConfirmMappings = async () => {
    if (!selectedFile) return;

    setIsLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('folder_mappings', JSON.stringify(folderMappings));

      const response = await fetch('/sequences/import?auto_download=false', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Import failed');
      }

      const data = await response.json();
      setPreviewData(data);
      setStep('preview');
    } catch (err) {
      console.error('Import with mappings error:', err);
      setError(err.message || 'Failed to import with folder mappings');
    } finally {
      setIsLoading(false);
    }
  };

  // Download missing prerolls from Community
  const handleDownloadMissing = async () => {
    if (!previewData?.match_results?.missing_prerolls) return;

    const downloadable = previewData.match_results.missing_prerolls.filter(p => p.downloadable);
    if (downloadable.length === 0) return;

    setStep('downloading');
    setDownloadProgress({ current: 0, total: downloadable.length, currentName: '' });
    setDownloadedPrerolls([]);
    setDownloadErrors([]);

    for (let i = 0; i < downloadable.length; i++) {
      const preroll = downloadable[i];
      setDownloadProgress({
        current: i + 1,
        total: downloadable.length,
        currentName: preroll.name
      });

      try {
        // Download from community prerolls
        const response = await fetch('/community-prerolls/download', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            preroll_id: preroll.community_id,
            title: preroll.name,
            category_id: null, // Let backend find/create appropriate category
            add_to_category: true
          })
        });

        if (response.ok) {
          const result = await response.json();
          setDownloadedPrerolls(prev => [...prev, {
            name: preroll.name,
            community_id: preroll.community_id,
            success: true,
            preroll_id: result.preroll_id
          }]);
        } else {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.detail || 'Download failed');
        }
      } catch (err) {
        console.error(`Failed to download ${preroll.name}:`, err);
        setDownloadErrors(prev => [...prev, {
          name: preroll.name,
          community_id: preroll.community_id,
          error: err.message
        }]);
      }
    }

    // Re-preview to get updated match results
    await handleRePreview();
  };

  // Re-preview after downloads to update match status
  const handleRePreview = async () => {
    if (!selectedFile) return;

    setIsLoading(true);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const response = await fetch('/sequences/import?auto_download=false', {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        setPreviewData(data);
      }
    } catch (err) {
      console.error('Re-preview error:', err);
    } finally {
      setIsLoading(false);
      setStep('ready');
    }
  };

  const handleConfirmImport = () => {
    if (!previewData) return;

    // Pass the imported blocks and metadata back to parent component
    const blocks = previewData.blocks || [];
    const metadata = {
      name: previewData.pattern_name,
      description: previewData.pattern_description || '',
      sequenceJson: previewData.sequence_json,
      matchResults: previewData.match_results
    };
    
    onImport(blocks, metadata);
    
    // Reset and close
    setSelectedFile(null);
    setPreviewData(null);
    setError(null);
    setStep('select');
    onClose();
  };

  // Handle downloading missing prerolls for .nexbundle files
  const handleBundleDownloadMissing = async () => {
    if (!previewData?.match_results?.missing_prerolls) return;

    const downloadable = previewData.match_results.missing_prerolls.filter(p => p.downloadable);
    if (downloadable.length === 0) return;

    setStep('downloading');
    setDownloadProgress({ current: 0, total: downloadable.length, currentName: '' });
    setDownloadedPrerolls([]);
    setDownloadErrors([]);

    for (let i = 0; i < downloadable.length; i++) {
      const preroll = downloadable[i];
      setDownloadProgress({
        current: i + 1,
        total: downloadable.length,
        currentName: preroll.name
      });

      try {
        const response = await fetch('/community-prerolls/download', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            preroll_id: preroll.community_id,
            title: preroll.name,
            category_id: null,
            add_to_category: true
          })
        });

        if (response.ok) {
          const result = await response.json();
          setDownloadedPrerolls(prev => [...prev, {
            name: preroll.name,
            community_id: preroll.community_id,
            success: true,
            preroll_id: result.preroll_id
          }]);
        } else {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.detail || 'Download failed');
        }
      } catch (err) {
        console.error(`Failed to download ${preroll.name}:`, err);
        setDownloadErrors(prev => [...prev, {
          name: preroll.name,
          community_id: preroll.community_id,
          error: err.message
        }]);
      }
    }

    // Re-preview the bundle to update match status
    await handleBundleRePreview();
  };

  // Re-preview the bundle after downloads
  const handleBundleRePreview = async () => {
    if (!selectedFile) return;

    setIsLoading(true);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const response = await fetch('/sequences/import?auto_download=false', {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        setPreviewData(data);
        // Stay on bundle-preview step (not 'ready') since bundles have their own flow
        setStep('bundle-preview');
      }
    } catch (err) {
      console.error('Bundle re-preview error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  // Confirm and save all sequences from the bundle
  const handleConfirmBundleImport = async () => {
    if (!previewData?.sequences) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch('/sequences/import-bundle-confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sequences: previewData.sequences
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Import failed');
      }

      const data = await response.json();
      
      // Notify parent of successful import
      if (onImport) {
        onImport(data);
      }
      
      // Reset and close
      setSelectedFile(null);
      setPreviewData(null);
      setError(null);
      setStep('select');
      onClose();
    } catch (err) {
      console.error('Bundle import error:', err);
      setError(err.message || 'Failed to import bundle');
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setSelectedFile(null);
    setPreviewData(null);
    setError(null);
    setStep('select');
    setDownloadProgress({ current: 0, total: 0, currentName: '' });
    setDownloadedPrerolls([]);
    setDownloadErrors([]);
  };

  if (!isOpen) return null;

  const downloadableCount = previewData?.match_results?.missing_prerolls?.filter(p => p.downloadable).length || 0;
  const matchedCount = previewData?.match_results?.matched || 0;
  const totalBlocks = previewData?.match_results?.total_blocks || 0;

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.7)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'auto',
        padding: '2rem',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && step !== 'downloading') onClose();
      }}
    >
      <div
        style={{
          backgroundColor: 'var(--card-bg)',
          borderRadius: '0.5rem',
          padding: '2rem',
          maxWidth: '750px',
          width: '100%',
          maxHeight: '90vh',
          overflowY: 'auto',
          border: '1px solid var(--border-color)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <h2 style={{ margin: 0, marginBottom: '1rem', color: 'var(--text-color)', fontSize: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Download size={24} /> Import Sequence Pattern
        </h2>

        {/* Step 1: File Selection */}
        {step === 'select' && (
          <>
            <div
              style={{
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                borderRadius: '0.5rem',
                padding: '1rem',
                marginBottom: '1.5rem',
                border: '1px solid rgba(16, 185, 129, 0.3)',
              }}
            >
              <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--text-color)', lineHeight: '1.6' }}>
                <strong>Import a pattern file or full bundle</strong>
              </p>
              <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.85rem', color: '#9ca3af', lineHeight: '1.5' }}>
                • <strong>.nexseq / .json</strong> - Pattern only (matches existing prerolls)<br/>
                • <strong>.zip bundle</strong> - Complete package with video files
              </p>
              <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.85rem', color: '#9ca3af', lineHeight: '1.5' }}>
                Missing prerolls with Community IDs can be downloaded automatically from the Community Prerolls library.
              </p>
            </div>

            <div style={{ marginBottom: '1.5rem' }}>
              <label
                style={{
                  display: 'block',
                  marginBottom: '0.5rem',
                  fontSize: '0.9rem',
                  color: 'var(--text-color)',
                  fontWeight: 'bold',
                }}
              >
                Select Pattern File or Bundle:
              </label>
              <input
                type="file"
                accept=".nexseq,.json,.zip,.nexbundle"
                onChange={handleFileSelect}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  backgroundColor: 'var(--bg-color)',
                  color: 'var(--text-color)',
                  border: '2px solid var(--border-color)',
                  borderRadius: '0.5rem',
                  fontSize: '0.9rem',
                }}
              />
              {selectedFile && (
                <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.85rem', color: '#10b981', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <Check size={14} /> Selected: {selectedFile.name} ({(selectedFile.size / 1024).toFixed(2)} KB)
                </p>
              )}
            </div>
          </>
        )}

        {/* Step 1.5: Folder Mapping for ZIP Bundles */}
        {step === 'folder-mapping' && bundleContents && (
          <>
            <div
              style={{
                backgroundColor: 'rgba(139, 92, 246, 0.1)',
                borderRadius: '0.5rem',
                padding: '1rem',
                marginBottom: '1.5rem',
                border: '1px solid rgba(139, 92, 246, 0.3)',
              }}
            >
              <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--text-color)', lineHeight: '1.6' }}>
                <strong>📂 Configure Import Destinations</strong>
              </p>
              <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.85rem', color: '#9ca3af', lineHeight: '1.5' }}>
                Choose where to import each folder and preroll from the bundle. You can select existing categories or create new ones.
              </p>
            </div>

            {/* Category Folders Section */}
            {bundleContents.categories && bundleContents.categories.length > 0 && (
              <div style={{ marginBottom: '1.5rem' }}>
                <div 
                  onClick={() => setExpandedSections(prev => ({ ...prev, categories: !prev.categories }))}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    cursor: 'pointer',
                    marginBottom: '0.75rem',
                    padding: '0.5rem',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderRadius: '0.25rem',
                    border: '1px solid rgba(16, 185, 129, 0.3)',
                  }}
                >
                  {expandedSections.categories ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                  <Folder size={18} style={{ color: '#10b981' }} />
                  <span style={{ fontWeight: 'bold', color: 'var(--text-color)', flex: 1 }}>
                    Category Folders ({bundleContents.categories.length})
                  </span>
                  <span style={{ fontSize: '0.8rem', color: '#9ca3af' }}>
                    For random blocks - entire folder contents
                  </span>
                </div>
                
                {expandedSections.categories && (
                  <div style={{ 
                    backgroundColor: 'var(--hover-bg)', 
                    borderRadius: '0.5rem', 
                    padding: '1rem',
                    border: '1px solid var(--border-color)',
                  }}>
                    {bundleContents.categories.map((cat, idx) => (
                      <div key={idx} style={{ 
                        display: 'flex', 
                        alignItems: 'center', 
                        gap: '1rem',
                        padding: '0.75rem',
                        borderBottom: idx < bundleContents.categories.length - 1 ? '1px solid var(--border-color)' : 'none',
                      }}>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 'bold', color: 'var(--text-color)', fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <FolderOpen size={16} style={{ color: '#10b981' }} />
                            {cat.name}
                          </div>
                          <div style={{ fontSize: '0.8rem', color: '#9ca3af', marginTop: '0.25rem' }}>
                            {cat.preroll_count} preroll{cat.preroll_count !== 1 ? 's' : ''}
                          </div>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span style={{ fontSize: '0.85rem', color: '#9ca3af' }}>→</span>
                          <select
                            value={folderMappings[`category:${cat.name}`] || `new:${cat.name}`}
                            onChange={(e) => handleMappingChange(`category:${cat.name}`, e.target.value)}
                            style={{
                              padding: '0.5rem',
                              backgroundColor: 'var(--bg-color)',
                              color: 'var(--text-color)',
                              border: '1px solid var(--border-color)',
                              borderRadius: '0.25rem',
                              minWidth: '200px',
                            }}
                          >
                            <option value={`new:${cat.name}`}>➕ Create: {cat.name}</option>
                            {availableCategories.map(c => (
                              <option key={c.id} value={c.id}>{c.name}</option>
                            ))}
                          </select>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Fixed Prerolls Section */}
            {bundleContents.fixed && bundleContents.fixed.length > 0 && (
              <div style={{ marginBottom: '1.5rem' }}>
                <div 
                  onClick={() => setExpandedSections(prev => ({ ...prev, fixed: !prev.fixed }))}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    cursor: 'pointer',
                    marginBottom: '0.75rem',
                    padding: '0.5rem',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderRadius: '0.25rem',
                    border: '1px solid rgba(59, 130, 246, 0.3)',
                  }}
                >
                  {expandedSections.fixed ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                  <FileText size={18} style={{ color: '#3b82f6' }} />
                  <span style={{ fontWeight: 'bold', color: 'var(--text-color)', flex: 1 }}>
                    Fixed Prerolls ({bundleContents.fixed.length})
                  </span>
                  <span style={{ fontSize: '0.8rem', color: '#9ca3af' }}>
                    Individual preroll files
                  </span>
                </div>
                
                {expandedSections.fixed && (
                  <div style={{ 
                    backgroundColor: 'var(--hover-bg)', 
                    borderRadius: '0.5rem', 
                    padding: '1rem',
                    border: '1px solid var(--border-color)',
                  }}>
                    {bundleContents.fixed.map((preroll, idx) => (
                      <div key={idx} style={{ 
                        display: 'flex', 
                        alignItems: 'center', 
                        gap: '1rem',
                        padding: '0.75rem',
                        borderBottom: idx < bundleContents.fixed.length - 1 ? '1px solid var(--border-color)' : 'none',
                      }}>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 'bold', color: 'var(--text-color)', fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <FileText size={16} style={{ color: '#3b82f6' }} />
                            {preroll.name}
                          </div>
                          {preroll.original_category && (
                            <div style={{ fontSize: '0.8rem', color: '#9ca3af', marginTop: '0.25rem' }}>
                              Originally in: {preroll.original_category}
                            </div>
                          )}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span style={{ fontSize: '0.85rem', color: '#9ca3af' }}>→</span>
                          <select
                            value={folderMappings[`fixed:${preroll.name}`] || ''}
                            onChange={(e) => handleMappingChange(`fixed:${preroll.name}`, e.target.value)}
                            style={{
                              padding: '0.5rem',
                              backgroundColor: 'var(--bg-color)',
                              color: 'var(--text-color)',
                              border: '1px solid var(--border-color)',
                              borderRadius: '0.25rem',
                              minWidth: '200px',
                            }}
                          >
                            <option value="new:Imported">➕ Create: Imported</option>
                            {availableCategories.map(c => (
                              <option key={c.id} value={c.id}>{c.name}</option>
                            ))}
                          </select>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Quick Actions */}
            <div style={{ 
              backgroundColor: 'rgba(245, 158, 11, 0.1)', 
              borderRadius: '0.5rem', 
              padding: '0.75rem',
              marginBottom: '1rem',
              border: '1px solid rgba(245, 158, 11, 0.3)',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              fontSize: '0.85rem',
              color: '#f59e0b'
            }}>
              <Lightbulb size={16} />
              <span>Tip: Categories that match the bundle folder names will be auto-selected. Use the dropdown to change destinations.</span>
            </div>

            {/* Preview Sequence Button - Only for ZIP bundles with sequence */}
            {bundleContents?.sequence && bundleContents.sequence.length > 0 && (
              <div style={{ 
                backgroundColor: 'rgba(139, 92, 246, 0.1)', 
                borderRadius: '0.5rem', 
                padding: '0.75rem',
                marginBottom: '1rem',
                border: '1px solid rgba(139, 92, 246, 0.3)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '0.5rem',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Play size={16} style={{ color: '#8b5cf6' }} />
                  <span style={{ fontSize: '0.85rem', color: '#8b5cf6' }}>
                    Preview the sequence as it will play ({bundleContents.sequence.length} block{bundleContents.sequence.length !== 1 ? 's' : ''})
                  </span>
                </div>
                <button
                  onClick={handleStartPreview}
                  style={{
                    padding: '0.5rem 1rem',
                    backgroundColor: '#8b5cf6',
                    color: 'white',
                    border: 'none',
                    borderRadius: '0.375rem',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    fontSize: '0.85rem',
                    fontWeight: '500',
                  }}
                >
                  <Play size={14} /> Preview Sequence
                </button>
              </div>
            )}

            {/* Sequence Preview Player Modal */}
            {showPreviewPlayer && previewPlaylist.length > 0 && (
              <div style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                backgroundColor: 'rgba(0, 0, 0, 0.9)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 10000,
              }}>
                {/* Close button */}
                <button
                  onClick={handleClosePreview}
                  style={{
                    position: 'absolute',
                    top: '1rem',
                    right: '1rem',
                    padding: '0.5rem',
                    backgroundColor: 'rgba(255, 255, 255, 0.1)',
                    color: 'white',
                    border: 'none',
                    borderRadius: '0.375rem',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    fontSize: '0.9rem',
                  }}
                >
                  <X size={20} /> Close
                </button>

                {/* Now Playing Info */}
                <div style={{
                  position: 'absolute',
                  top: '1rem',
                  left: '1rem',
                  color: 'white',
                  backgroundColor: 'rgba(0, 0, 0, 0.7)',
                  padding: '0.75rem 1rem',
                  borderRadius: '0.5rem',
                }}>
                  <div style={{ fontSize: '0.8rem', color: '#9ca3af', marginBottom: '0.25rem' }}>
                    Now Playing ({currentPreviewIndex + 1} of {previewPlaylist.length})
                  </div>
                  <div style={{ fontWeight: 'bold', fontSize: '1.1rem' }}>
                    {previewPlaylist[currentPreviewIndex]?.name}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: '#9ca3af', marginTop: '0.25rem' }}>
                    {previewPlaylist[currentPreviewIndex]?.type === 'fixed' 
                      ? '🎯 Fixed Block' 
                      : `🎲 Random from ${previewPlaylist[currentPreviewIndex]?.category} (${previewPlaylist[currentPreviewIndex]?.totalInCategory || '?'} available)`}
                  </div>
                </div>

                {/* Video Player */}
                <video
                  ref={videoRef}
                  src={previewPlaylist[currentPreviewIndex]?.url}
                  autoPlay
                  onEnded={handleVideoEnded}
                  onPlay={() => setIsPlaying(true)}
                  onPause={() => setIsPlaying(false)}
                  style={{
                    maxWidth: '90%',
                    maxHeight: '70vh',
                    borderRadius: '0.5rem',
                    boxShadow: '0 0 40px rgba(139, 92, 246, 0.3)',
                  }}
                />

                {/* Playback Controls */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '1rem',
                  marginTop: '1.5rem',
                  padding: '0.75rem 1.5rem',
                  backgroundColor: 'rgba(255, 255, 255, 0.1)',
                  borderRadius: '2rem',
                }}>
                  <button
                    onClick={handlePrevVideo}
                    disabled={currentPreviewIndex === 0}
                    style={{
                      padding: '0.75rem',
                      backgroundColor: currentPreviewIndex === 0 ? 'rgba(255, 255, 255, 0.1)' : 'rgba(139, 92, 246, 0.3)',
                      color: currentPreviewIndex === 0 ? '#666' : 'white',
                      border: 'none',
                      borderRadius: '50%',
                      cursor: currentPreviewIndex === 0 ? 'not-allowed' : 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <SkipBack size={20} />
                  </button>

                  <button
                    onClick={togglePlayPause}
                    style={{
                      padding: '1rem',
                      backgroundColor: '#8b5cf6',
                      color: 'white',
                      border: 'none',
                      borderRadius: '50%',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    {isPlaying ? <Pause size={24} /> : <Play size={24} />}
                  </button>

                  <button
                    onClick={handleNextVideo}
                    disabled={currentPreviewIndex === previewPlaylist.length - 1}
                    style={{
                      padding: '0.75rem',
                      backgroundColor: currentPreviewIndex === previewPlaylist.length - 1 ? 'rgba(255, 255, 255, 0.1)' : 'rgba(139, 92, 246, 0.3)',
                      color: currentPreviewIndex === previewPlaylist.length - 1 ? '#666' : 'white',
                      border: 'none',
                      borderRadius: '50%',
                      cursor: currentPreviewIndex === previewPlaylist.length - 1 ? 'not-allowed' : 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <SkipForward size={20} />
                  </button>
                </div>

                {/* Sequence Progress */}
                <div style={{
                  display: 'flex',
                  gap: '0.5rem',
                  marginTop: '1rem',
                  flexWrap: 'wrap',
                  justifyContent: 'center',
                  maxWidth: '80%',
                }}>
                  {previewPlaylist.map((item, idx) => (
                    <div
                      key={idx}
                      onClick={() => {
                        setCurrentPreviewIndex(idx);
                        setIsPlaying(true);
                      }}
                      style={{
                        width: idx === currentPreviewIndex ? '2rem' : '0.75rem',
                        height: '0.75rem',
                        borderRadius: '0.375rem',
                        backgroundColor: idx === currentPreviewIndex 
                          ? '#8b5cf6' 
                          : idx < currentPreviewIndex 
                            ? 'rgba(139, 92, 246, 0.5)' 
                            : 'rgba(255, 255, 255, 0.3)',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease',
                      }}
                      title={item.name}
                    />
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {/* Step 2: Preview Results */}
        {(step === 'preview' || step === 'ready') && previewData && (
          <>
            {/* Pattern Info */}
            <div
              style={{
                backgroundColor: 'var(--hover-bg)',
                borderRadius: '0.5rem',
                padding: '1.5rem',
                marginBottom: '1.5rem',
                border: '1px solid var(--border-color)',
              }}
            >
              <h3 style={{ margin: 0, marginBottom: '1rem', fontSize: '1.1rem', color: 'var(--text-color)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <ClipboardList size={18} /> Pattern Preview
              </h3>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
                <div>
                  <div style={{ fontSize: '0.8rem', color: '#9ca3af', marginBottom: '0.25rem' }}>Pattern Name:</div>
                  <div style={{ fontSize: '0.95rem', color: 'var(--text-color)', fontWeight: 'bold' }}>
                    {previewData.pattern_name}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '0.8rem', color: '#9ca3af', marginBottom: '0.25rem' }}>Created By:</div>
                  <div style={{ fontSize: '0.95rem', color: 'var(--text-color)', fontWeight: 'bold' }}>
                    {previewData.created_by}
                  </div>
                </div>
              </div>

              {/* Match Statistics */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(4, 1fr)',
                  gap: '0.75rem',
                  marginTop: '1rem',
                }}
              >
                <div
                  style={{
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderRadius: '0.5rem',
                    padding: '0.75rem',
                    textAlign: 'center',
                    border: '1px solid rgba(16, 185, 129, 0.3)',
                  }}
                >
                  <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#10b981' }}>
                    {previewData.match_results.matched}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: '#9ca3af', marginTop: '0.25rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.25rem' }}><CheckCircle size={12} /> Matched</div>
                </div>
                <div
                  style={{
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderRadius: '0.5rem',
                    padding: '0.75rem',
                    textAlign: 'center',
                    border: '1px solid rgba(59, 130, 246, 0.3)',
                  }}
                >
                  <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#3b82f6' }}>
                    {downloadableCount}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: '#9ca3af', marginTop: '0.25rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.25rem' }}><CloudDownload size={12} /> Downloadable</div>
                </div>
                <div
                  style={{
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    borderRadius: '0.5rem',
                    padding: '0.75rem',
                    textAlign: 'center',
                    border: '1px solid rgba(239, 68, 68, 0.3)',
                  }}
                >
                  <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#ef4444' }}>
                    {previewData.match_results.unmatched - downloadableCount}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: '#9ca3af', marginTop: '0.25rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.25rem' }}><XCircle size={12} /> Missing</div>
                </div>
                <div
                  style={{
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderRadius: '0.5rem',
                    padding: '0.75rem',
                    textAlign: 'center',
                    border: '1px solid rgba(102, 126, 234, 0.3)',
                  }}
                >
                  <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#667eea' }}>
                    {previewData.match_results.total_blocks}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: '#9ca3af', marginTop: '0.25rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.25rem' }}><Package size={12} /> Total</div>
                </div>
              </div>
            </div>

            {/* Download from Community Option - Only show if there are downloadable prerolls */}
            {downloadableCount > 0 && step === 'preview' && (
              <div
                style={{
                  backgroundColor: 'rgba(59, 130, 246, 0.1)',
                  borderRadius: '0.5rem',
                  padding: '1rem',
                  marginBottom: '1.5rem',
                  border: '2px solid rgba(59, 130, 246, 0.4)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem' }}>
                  <Cloud size={20} style={{ color: '#3b82f6' }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '0.95rem', fontWeight: 'bold', color: 'var(--text-color)' }}>
                      {downloadableCount} preroll{downloadableCount !== 1 ? 's' : ''} available from Community
                    </div>
                    <div style={{ fontSize: '0.8rem', color: '#9ca3af' }}>
                      These prerolls have Community IDs and can be downloaded automatically
                    </div>
                  </div>
                </div>

                {/* List of downloadable prerolls */}
                <div style={{ 
                  maxHeight: '120px', 
                  overflowY: 'auto', 
                  marginBottom: '0.75rem',
                  backgroundColor: 'rgba(0,0,0,0.2)',
                  borderRadius: '0.25rem',
                  padding: '0.5rem'
                }}>
                  {previewData.match_results.missing_prerolls
                    .filter(p => p.downloadable)
                    .map((preroll, idx) => (
                      <div key={idx} style={{ 
                        padding: '0.35rem 0', 
                        fontSize: '0.8rem', 
                        color: '#9ca3af',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        borderBottom: idx < downloadableCount - 1 ? '1px solid rgba(59, 130, 246, 0.2)' : 'none'
                      }}>
                        <Download size={12} style={{ color: '#3b82f6' }} />
                        <span style={{ flex: 1 }}>{preroll.name}</span>
                        {preroll.category && (
                          <span style={{ fontSize: '0.7rem', color: '#6b7280' }}>({preroll.category})</span>
                        )}
                      </div>
                    ))}
                </div>

                <button
                  onClick={handleDownloadMissing}
                  style={{
                    width: '100%',
                    padding: '0.75rem',
                    backgroundColor: '#3b82f6',
                    color: 'white',
                    border: 'none',
                    borderRadius: '0.5rem',
                    cursor: 'pointer',
                    fontSize: '0.95rem',
                    fontWeight: 'bold',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '0.5rem',
                  }}
                >
                  <CloudDownload size={18} /> Download {downloadableCount} Missing Preroll{downloadableCount !== 1 ? 's' : ''}
                </button>
              </div>
            )}

            {/* Downloaded Results - Show after downloads complete */}
            {step === 'ready' && (downloadedPrerolls.length > 0 || downloadErrors.length > 0) && (
              <div
                style={{
                  backgroundColor: 'rgba(16, 185, 129, 0.1)',
                  borderRadius: '0.5rem',
                  padding: '1rem',
                  marginBottom: '1.5rem',
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                  <CheckCircle size={18} style={{ color: '#10b981' }} />
                  <span style={{ fontWeight: 'bold', color: '#10b981' }}>
                    Downloaded {downloadedPrerolls.length} preroll{downloadedPrerolls.length !== 1 ? 's' : ''}
                  </span>
                </div>
                
                {downloadErrors.length > 0 && (
                  <div style={{ 
                    backgroundColor: 'rgba(239, 68, 68, 0.1)', 
                    borderRadius: '0.25rem', 
                    padding: '0.5rem',
                    marginTop: '0.5rem'
                  }}>
                    <div style={{ fontSize: '0.8rem', color: '#ef4444', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      <AlertTriangle size={14} /> {downloadErrors.length} download{downloadErrors.length !== 1 ? 's' : ''} failed
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Bundle Import Results */}
            {previewData.import_results && previewData.import_results.bundle_mode && (
              <div
                style={{
                  backgroundColor: 'rgba(139, 92, 246, 0.1)',
                  borderRadius: '0.5rem',
                  padding: '1rem',
                  marginBottom: '1.5rem',
                  border: '1px solid rgba(139, 92, 246, 0.3)',
                }}
              >
                <h4 style={{ margin: 0, marginBottom: '0.75rem', fontSize: '0.95rem', color: '#8b5cf6', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Package size={16} /> Bundle Import Results
                </h4>
                
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  <div>
                    <div style={{ fontSize: '0.8rem', color: '#9ca3af', marginBottom: '0.25rem' }}>Prerolls Imported:</div>
                    <div style={{ fontSize: '1.2rem', color: '#8b5cf6', fontWeight: 'bold' }}>
                      {previewData.import_results.prerolls_imported_count}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.8rem', color: '#9ca3af', marginBottom: '0.25rem' }}>New Categories:</div>
                    <div style={{ fontSize: '1.2rem', color: '#8b5cf6', fontWeight: 'bold' }}>
                      {previewData.import_results.categories_imported_count}
                    </div>
                  </div>
                </div>

                {previewData.import_results.imported_prerolls.length > 0 && (
                  <div style={{ marginTop: '1rem' }}>
                    <div style={{ fontSize: '0.85rem', color: 'var(--text-color)', marginBottom: '0.5rem' }}>
                      <strong>Imported video files:</strong>
                    </div>
                    <div style={{ maxHeight: '150px', overflowY: 'auto', fontSize: '0.8rem', color: '#9ca3af' }}>
                      {previewData.import_results.imported_prerolls.map((item, idx) => (
                        <div key={idx} style={{ padding: '0.25rem 0', borderBottom: '1px solid rgba(139, 92, 246, 0.1)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                          <span style={{ color: item.type === 'category' ? '#10b981' : '#3b82f6', display: 'inline-flex' }}>
                            {item.type === 'category' ? <Folder size={12} /> : <FileText size={12} />}
                          </span>
                          {item.name}
                          <span style={{ marginLeft: '0.5rem', color: '#8b5cf6', fontSize: '0.75rem' }}>
                            ({item.category})
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div
                  style={{
                    marginTop: '0.75rem',
                    fontSize: '0.75rem',
                    color: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    padding: '0.5rem',
                    borderRadius: '0.25rem',
                    border: '1px solid rgba(16, 185, 129, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.35rem',
                  }}
                >
                  <CheckCircle size={14} /> Video files have been imported to your library. Duplicates were automatically skipped.
                </div>
              </div>
            )}

            {/* Missing Items Warning */}
            {(previewData.match_results.missing_categories.length > 0 ||
              previewData.match_results.missing_prerolls.filter(p => !p.downloadable).length > 0) && (
              <div
                style={{
                  backgroundColor: 'rgba(245, 158, 11, 0.1)',
                  borderRadius: '0.5rem',
                  padding: '1rem',
                  marginBottom: '1.5rem',
                  border: '1px solid rgba(245, 158, 11, 0.3)',
                }}
              >
                <h4 style={{ margin: 0, marginBottom: '0.75rem', fontSize: '0.95rem', color: '#f59e0b', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <AlertTriangle size={16} /> Unavailable Items
                </h4>

                {previewData.match_results.missing_categories.length > 0 && (
                  <div style={{ marginBottom: '0.75rem' }}>
                    <div style={{ fontSize: '0.85rem', color: 'var(--text-color)', marginBottom: '0.5rem' }}>
                      <strong>Categories not found:</strong>
                    </div>
                    <ul style={{ margin: 0, paddingLeft: '1.5rem', fontSize: '0.8rem', color: '#9ca3af' }}>
                      {previewData.match_results.missing_categories.map((cat, idx) => (
                        <li key={idx}>{cat}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {previewData.match_results.missing_prerolls.filter(p => !p.downloadable).length > 0 && (
                  <div>
                    <div style={{ fontSize: '0.85rem', color: 'var(--text-color)', marginBottom: '0.5rem' }}>
                      <strong>Prerolls not available:</strong>
                    </div>
                    <ul style={{ margin: 0, paddingLeft: '1.5rem', fontSize: '0.8rem', color: '#9ca3af' }}>
                      {previewData.match_results.missing_prerolls
                        .filter(p => !p.downloadable)
                        .slice(0, 5)
                        .map((preroll, idx) => (
                          <li key={idx}>
                            <span style={{ color: '#ef4444', display: 'inline-flex', verticalAlign: 'middle', marginRight: '0.25rem' }}><XCircle size={12} /></span> 
                            {preroll.name}
                            <span style={{ marginLeft: '0.5rem', color: '#ef4444', fontSize: '0.75rem' }}>
                              ({preroll.reason || 'Not in community library'})
                            </span>
                          </li>
                        ))}
                      {previewData.match_results.missing_prerolls.filter(p => !p.downloadable).length > 5 && (
                        <li style={{ color: '#f59e0b' }}>
                          +{previewData.match_results.missing_prerolls.filter(p => !p.downloadable).length - 5} more...
                        </li>
                      )}
                    </ul>
                  </div>
                )}

                <p style={{ margin: '0.75rem 0 0 0', fontSize: '0.8rem', color: '#9ca3af', display: 'flex', alignItems: 'flex-start', gap: '0.35rem' }}>
                  <Lightbulb size={14} style={{ marginTop: '0.1rem', flexShrink: 0 }} />
                  <span>These items don't have Community IDs. You may need to manually add similar prerolls or create new categories.</span>
                </p>
              </div>
            )}
          </>
        )}

        {/* Step: Bundle Preview - Shows all sequences from .nexbundle with their match status */}
        {step === 'bundle-preview' && previewData && (
          <>
            <div
              style={{
                backgroundColor: 'var(--hover-bg)',
                borderRadius: '0.5rem',
                padding: '1.5rem',
                marginBottom: '1.5rem',
                border: '1px solid var(--border-color)',
              }}
            >
              <h3 style={{ margin: 0, marginBottom: '1rem', fontSize: '1.1rem', color: 'var(--text-color)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Package size={18} /> Bundle Preview: {previewData.sequences?.length || 0} Sequences
              </h3>

              {/* Match Statistics */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(4, 1fr)',
                  gap: '0.75rem',
                  marginBottom: '1rem',
                }}
              >
                <div style={{ backgroundColor: 'rgba(16, 185, 129, 0.1)', borderRadius: '0.5rem', padding: '0.75rem', textAlign: 'center', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
                  <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#10b981' }}>{previewData.match_results?.matched || 0}</div>
                  <div style={{ fontSize: '0.7rem', color: '#9ca3af', marginTop: '0.25rem' }}>Matched</div>
                </div>
                <div style={{ backgroundColor: 'rgba(245, 158, 11, 0.1)', borderRadius: '0.5rem', padding: '0.75rem', textAlign: 'center', border: '1px solid rgba(245, 158, 11, 0.3)' }}>
                  <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#f59e0b' }}>{previewData.match_results?.downloadable || 0}</div>
                  <div style={{ fontSize: '0.7rem', color: '#9ca3af', marginTop: '0.25rem' }}>Downloadable</div>
                </div>
                <div style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', borderRadius: '0.5rem', padding: '0.75rem', textAlign: 'center', border: '1px solid rgba(239, 68, 68, 0.3)' }}>
                  <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#ef4444' }}>{(previewData.match_results?.unmatched || 0) - (previewData.match_results?.downloadable || 0)}</div>
                  <div style={{ fontSize: '0.7rem', color: '#9ca3af', marginTop: '0.25rem' }}>Missing</div>
                </div>
                <div style={{ backgroundColor: 'rgba(102, 126, 234, 0.1)', borderRadius: '0.5rem', padding: '0.75rem', textAlign: 'center', border: '1px solid rgba(102, 126, 234, 0.3)' }}>
                  <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#667eea' }}>{previewData.match_results?.total_blocks || 0}</div>
                  <div style={{ fontSize: '0.7rem', color: '#9ca3af', marginTop: '0.25rem' }}>Total Blocks</div>
                </div>
              </div>

              {/* Sequence List */}
              <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
                {previewData.sequences?.map((seq, idx) => (
                  <div
                    key={idx}
                    style={{
                      backgroundColor: 'rgba(0,0,0,0.2)',
                      borderRadius: '0.5rem',
                      padding: '1rem',
                      marginBottom: idx < previewData.sequences.length - 1 ? '0.75rem' : 0,
                      border: seq.stats?.unmatched > 0 ? '1px solid rgba(245, 158, 11, 0.5)' : '1px solid var(--border-color)',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                      <div style={{ fontWeight: 'bold', color: 'var(--text-color)' }}>{seq.name}</div>
                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <span style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem', borderRadius: '0.25rem', backgroundColor: 'rgba(16, 185, 129, 0.2)', color: '#10b981' }}>
                          {seq.stats?.matched || 0} matched
                        </span>
                        {seq.stats?.unmatched > 0 && (
                          <span style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem', borderRadius: '0.25rem', backgroundColor: 'rgba(245, 158, 11, 0.2)', color: '#f59e0b' }}>
                            {seq.stats?.unmatched || 0} missing
                          </span>
                        )}
                      </div>
                    </div>
                    {seq.description && (
                      <div style={{ fontSize: '0.8rem', color: '#9ca3af', marginBottom: '0.5rem' }}>{seq.description}</div>
                    )}
                    {seq.missing_prerolls && seq.missing_prerolls.length > 0 && (
                      <div style={{ fontSize: '0.75rem', color: '#f59e0b', display: 'flex', alignItems: 'flex-start', gap: '0.35rem' }}>
                        <AlertTriangle size={12} style={{ marginTop: '0.15rem', flexShrink: 0 }} />
                        <span>Missing: {seq.missing_prerolls.map(p => p.name).join(', ')}</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Download from Community Option */}
            {previewData.match_results?.downloadable > 0 && (
              <div
                style={{
                  backgroundColor: 'rgba(59, 130, 246, 0.1)',
                  borderRadius: '0.5rem',
                  padding: '1rem',
                  marginBottom: '1.5rem',
                  border: '2px solid rgba(59, 130, 246, 0.4)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem' }}>
                  <Cloud size={20} style={{ color: '#3b82f6' }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '0.95rem', fontWeight: 'bold', color: 'var(--text-color)' }}>
                      {previewData.match_results.downloadable} preroll{previewData.match_results.downloadable !== 1 ? 's' : ''} available from Community
                    </div>
                    <div style={{ fontSize: '0.8rem', color: '#9ca3af' }}>
                      Download missing prerolls before importing for complete sequences
                    </div>
                  </div>
                </div>

                <div style={{ maxHeight: '100px', overflowY: 'auto', marginBottom: '0.75rem', backgroundColor: 'rgba(0,0,0,0.2)', borderRadius: '0.25rem', padding: '0.5rem' }}>
                  {previewData.match_results.missing_prerolls
                    ?.filter(p => p.downloadable)
                    .map((preroll, idx) => (
                      <div key={idx} style={{ padding: '0.25rem 0', fontSize: '0.8rem', color: '#9ca3af', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <Download size={12} style={{ color: '#3b82f6' }} />
                        <span>{preroll.name}</span>
                        <span style={{ fontSize: '0.7rem', color: '#666' }}>({preroll.sequence_name})</span>
                      </div>
                    ))}
                </div>

                <button
                  onClick={handleBundleDownloadMissing}
                  disabled={isLoading}
                  style={{
                    width: '100%',
                    padding: '0.75rem 1rem',
                    backgroundColor: isLoading ? '#9ca3af' : '#3b82f6',
                    color: 'white',
                    border: 'none',
                    borderRadius: '0.5rem',
                    cursor: isLoading ? 'not-allowed' : 'pointer',
                    fontSize: '0.9rem',
                    fontWeight: 'bold',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '0.5rem',
                  }}
                >
                  {isLoading ? <><Loader2 size={16} className="spin" /> Downloading...</> : <><Download size={16} /> Download All from Community</>}
                </button>
              </div>
            )}

            {/* Warning for unavailable prerolls */}
            {previewData.match_results?.missing_prerolls?.filter(p => !p.downloadable).length > 0 && (
              <div
                style={{
                  backgroundColor: 'rgba(239, 68, 68, 0.1)',
                  borderRadius: '0.5rem',
                  padding: '1rem',
                  marginBottom: '1.5rem',
                  border: '1px solid rgba(239, 68, 68, 0.3)',
                }}
              >
                <div style={{ fontSize: '0.9rem', fontWeight: 'bold', color: '#ef4444', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <AlertTriangle size={16} /> {previewData.match_results.missing_prerolls.filter(p => !p.downloadable).length} prerolls cannot be downloaded
                </div>
                <div style={{ fontSize: '0.8rem', color: '#9ca3af' }}>
                  These prerolls don't have Community IDs and will show as "None selected" after import. You may need to manually select replacements.
                </div>
              </div>
            )}
          </>
        )}

        {/* Step 3: Downloading Progress */}
        {step === 'downloading' && (
          <div
            style={{
              backgroundColor: 'rgba(59, 130, 246, 0.1)',
              borderRadius: '0.5rem',
              padding: '2rem',
              marginBottom: '1.5rem',
              border: '2px solid rgba(59, 130, 246, 0.4)',
              textAlign: 'center',
            }}
          >
            <Loader2 size={48} className="spin" style={{ color: '#3b82f6', marginBottom: '1rem' }} />
            <h3 style={{ margin: 0, marginBottom: '0.5rem', color: 'var(--text-color)' }}>
              Downloading Prerolls from Community
            </h3>
            <p style={{ margin: 0, marginBottom: '1rem', color: '#9ca3af', fontSize: '0.9rem' }}>
              {downloadProgress.current} of {downloadProgress.total} complete
            </p>
            
            {/* Progress Bar */}
            <div style={{
              width: '100%',
              height: '8px',
              backgroundColor: 'rgba(59, 130, 246, 0.2)',
              borderRadius: '4px',
              overflow: 'hidden',
              marginBottom: '1rem'
            }}>
              <div style={{
                width: `${(downloadProgress.current / downloadProgress.total) * 100}%`,
                height: '100%',
                backgroundColor: '#3b82f6',
                transition: 'width 0.3s ease'
              }} />
            </div>

            {downloadProgress.currentName && (
              <p style={{ margin: 0, color: '#3b82f6', fontSize: '0.85rem' }}>
                Downloading: {downloadProgress.currentName}
              </p>
            )}
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div
            style={{
              backgroundColor: 'rgba(239, 68, 68, 0.1)',
              borderRadius: '0.5rem',
              padding: '1rem',
              marginBottom: '1.5rem',
              border: '1px solid rgba(239, 68, 68, 0.3)',
            }}
          >
            <p style={{ margin: 0, fontSize: '0.9rem', color: '#ef4444', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <AlertTriangle size={16} /> {error}
            </p>
          </div>
        )}

        {/* Action Buttons */}
        <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end', flexWrap: 'wrap' }}>
          {step === 'select' && (
            <>
              <button
                onClick={onClose}
                style={{
                  padding: '0.75rem 1.5rem',
                  backgroundColor: 'transparent',
                  color: 'var(--text-color)',
                  border: '2px solid var(--border-color)',
                  borderRadius: '0.5rem',
                  cursor: 'pointer',
                  fontSize: '1rem',
                }}
              >
                Cancel
              </button>
              <button
                onClick={handlePreview}
                disabled={!selectedFile || isLoading}
                style={{
                  padding: '0.75rem 1.5rem',
                  backgroundColor: !selectedFile || isLoading ? '#9ca3af' : '#667eea',
                  color: 'white',
                  border: 'none',
                  borderRadius: '0.5rem',
                  cursor: !selectedFile || isLoading ? 'not-allowed' : 'pointer',
                  fontSize: '1rem',
                  fontWeight: 'bold',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                }}
              >
                {isLoading ? <><Loader2 size={16} className="spin" /> Analyzing...</> : <><Eye size={16} /> Preview Import</>}
              </button>
            </>
          )}

          {step === 'folder-mapping' && (
            <>
              <button
                onClick={handleReset}
                style={{
                  padding: '0.75rem 1.5rem',
                  backgroundColor: 'transparent',
                  color: 'var(--text-color)',
                  border: '2px solid var(--border-color)',
                  borderRadius: '0.5rem',
                  cursor: 'pointer',
                  fontSize: '1rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                }}
              >
                <ArrowLeft size={16} /> Start Over
              </button>
              <button
                onClick={handleConfirmMappings}
                disabled={isLoading}
                style={{
                  padding: '0.75rem 1.5rem',
                  backgroundColor: isLoading ? '#9ca3af' : '#10b981',
                  color: 'white',
                  border: 'none',
                  borderRadius: '0.5rem',
                  cursor: isLoading ? 'not-allowed' : 'pointer',
                  fontSize: '1rem',
                  fontWeight: 'bold',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                }}
              >
                {isLoading ? <><Loader2 size={16} className="spin" /> Importing...</> : <><CheckCircle size={16} /> Import with Mappings</>}
              </button>
            </>
          )}

          {step === 'bundle-preview' && (
            <>
              <button
                onClick={handleReset}
                style={{
                  padding: '0.75rem 1.5rem',
                  backgroundColor: 'transparent',
                  color: 'var(--text-color)',
                  border: '2px solid var(--border-color)',
                  borderRadius: '0.5rem',
                  cursor: 'pointer',
                  fontSize: '1rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                }}
              >
                <ArrowLeft size={16} /> Start Over
              </button>
              <button
                onClick={handleConfirmBundleImport}
                disabled={isLoading}
                style={{
                  padding: '0.75rem 1.5rem',
                  backgroundColor: isLoading ? '#9ca3af' : '#10b981',
                  color: 'white',
                  border: 'none',
                  borderRadius: '0.5rem',
                  cursor: isLoading ? 'not-allowed' : 'pointer',
                  fontSize: '1rem',
                  fontWeight: 'bold',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                }}
              >
                {isLoading ? (
                  <><Loader2 size={16} className="spin" /> Importing...</>
                ) : (
                  <><CheckCircle size={16} /> Import {previewData?.sequences?.length || 0} Sequences</>
                )}
              </button>
            </>
          )}

          {(step === 'preview' || step === 'ready') && (
            <>
              <button
                onClick={handleReset}
                style={{
                  padding: '0.75rem 1.5rem',
                  backgroundColor: 'transparent',
                  color: 'var(--text-color)',
                  border: '2px solid var(--border-color)',
                  borderRadius: '0.5rem',
                  cursor: 'pointer',
                  fontSize: '1rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                }}
              >
                <ArrowLeft size={16} /> Start Over
              </button>
              
              {step === 'preview' && downloadableCount > 0 && (
                <button
                  onClick={handleConfirmImport}
                  style={{
                    padding: '0.75rem 1.5rem',
                    backgroundColor: '#6b7280',
                    color: 'white',
                    border: 'none',
                    borderRadius: '0.5rem',
                    cursor: 'pointer',
                    fontSize: '1rem',
                    fontWeight: 'bold',
                  }}
                >
                  Skip Downloads
                </button>
              )}
              
              <button
                onClick={handleConfirmImport}
                disabled={!previewData?.blocks || previewData.blocks.length === 0}
                style={{
                  padding: '0.75rem 1.5rem',
                  backgroundColor: (!previewData?.blocks || previewData.blocks.length === 0) ? '#9ca3af' : '#10b981',
                  color: 'white',
                  border: 'none',
                  borderRadius: '0.5rem',
                  cursor: (!previewData?.blocks || previewData.blocks.length === 0) ? 'not-allowed' : 'pointer',
                  fontSize: '1rem',
                  fontWeight: 'bold',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                }}
              >
                <CheckCircle size={16} /> {step === 'ready' ? 'Complete Import' : 'Import Pattern'}
              </button>
            </>
          )}

          {step === 'downloading' && (
            <button
              disabled
              style={{
                padding: '0.75rem 1.5rem',
                backgroundColor: '#9ca3af',
                color: 'white',
                border: 'none',
                borderRadius: '0.5rem',
                cursor: 'not-allowed',
                fontSize: '1rem',
                fontWeight: 'bold',
              }}
            >
              Downloading...
            </button>
          )}
        </div>

        {/* Help Text */}
        {step === 'select' && (
          <div
            style={{
              marginTop: '1.5rem',
              paddingTop: '1.5rem',
              borderTop: '1px solid var(--border-color)',
              fontSize: '0.8rem',
              color: '#9ca3af',
            }}
          >
            <p style={{ margin: 0, display: 'flex', alignItems: 'flex-start', gap: '0.35rem' }}>
              <Lightbulb size={14} style={{ marginTop: '0.1rem', flexShrink: 0 }} />
              <span><strong>Tip:</strong> Patterns exported with "Community IDs" allow automatic download of missing prerolls. ZIP bundles include all video files for complete offline transfer.</span>
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default PatternImport;
