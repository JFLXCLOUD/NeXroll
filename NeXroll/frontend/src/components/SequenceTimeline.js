import React from 'react';
import { 
  Film, Shuffle, ListOrdered, Clock, Play, Layers, 
  GripVertical, Timer, BarChart3, Clapperboard
} from 'lucide-react';

/**
 * SequenceTimeline - Timeline visualization for sequence blocks
 * Shows thumbnail strips with duration markers and color-coded block types
 * 
 * Props:
 * - blocks: Array of sequence blocks
 * - categories: Array of available categories
 * - prerolls: Array of all prerolls
 * - onBlockClick: Function called when a block is clicked
 */
const SequenceTimeline = ({ blocks = [], categories = [], prerolls = [], onBlockClick }) => {
  // Calculate total duration and individual block durations
  const calculateBlockDuration = (block) => {
    if (block.type === 'preroll') {
      const preroll = prerolls.find((p) => p.id === block.preroll_id);
      return preroll?.duration || 30; // Default 30s if unknown
    } else if (block.type === 'fixed') {
      // Fixed block - sum durations of specific prerolls
      if (!block.preroll_ids || block.preroll_ids.length === 0) return 0;
      return block.preroll_ids.reduce((sum, id) => {
        const preroll = prerolls.find((p) => p.id === id);
        return sum + (preroll?.duration || 30);
      }, 0);
    } else if (block.type === 'random' || block.type === 'sequential') {
      const categoryPrerolls = prerolls.filter((p) => p.category_id === block.category_id);
      const avgDuration = categoryPrerolls.reduce((sum, p) => sum + (p.duration || 30), 0) / (categoryPrerolls.length || 1);
      return avgDuration * (block.count || 1);
    } else if (block.type === 'queue') {
      // Estimate: average preroll is 30s, assume 3 in queue
      return 90;
    } else if (block.type === 'sequence') {
      // Nested sequence: would need recursive calculation, use estimate
      return 120;
    } else if (block.type === 'separator') {
      return 0;
    }
    return 30;
  };

  const blocksWithDurations = blocks.map((block) => ({
    ...block,
    duration: calculateBlockDuration(block),
  }));

  const totalDuration = blocksWithDurations.reduce((sum, b) => sum + b.duration, 0);
  const totalPrerolls = blocks.reduce((sum, block) => {
    if (block.type === 'fixed') return sum + (block.preroll_ids?.length || 0);
    if (block.type === 'random') return sum + (block.count || 1);
    if (block.type === 'preroll') return sum + 1;
    return sum;
  }, 0);

  // Format duration as MM:SS
  const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Get block color based on type
  const getBlockColor = (type) => {
    const colors = {
      preroll: { bg: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', solid: '#667eea' },
      fixed: { bg: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)', solid: '#f5576c' },
      random: { bg: 'linear-gradient(135deg, #f5af19 0%, #f12711 100%)', solid: '#f59e0b' },
      sequential: { bg: 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)', solid: '#10b981' },
      queue: { bg: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)', solid: '#ec4899' },
      sequence: { bg: 'linear-gradient(135deg, #a18cd1 0%, #fbc2eb 100%)', solid: '#8b5cf6' },
      separator: { bg: '#6b7280', solid: '#6b7280' },
    };
    return colors[type] || { bg: '#9ca3af', solid: '#9ca3af' };
  };

  // Get category name for a block
  const getCategoryName = (block) => {
    if (block.type === 'preroll') {
      const preroll = prerolls.find((p) => p.id === block.preroll_id);
      return preroll?.display_name || preroll?.filename || 'Unknown';
    } else if (block.type === 'fixed') {
      const count = block.preroll_ids?.length || 0;
      return `${count} Fixed Preroll${count !== 1 ? 's' : ''}`;
    } else if (block.type === 'random' || block.type === 'sequential') {
      const category = categories.find((c) => c.id === block.category_id);
      return category?.name || 'Unknown Category';
    } else if (block.type === 'queue') {
      return 'Queue Items';
    } else if (block.type === 'sequence') {
      return block.sequence_name || 'Nested Sequence';
    } else if (block.type === 'separator') {
      return 'Divider';
    }
    return 'Unknown';
  };

  // Get thumbnail for a block
  const getThumbnail = (block) => {
    if (block.type === 'preroll') {
      const preroll = prerolls.find((p) => p.id === block.preroll_id);
      return preroll?.thumbnail;
    } else if (block.type === 'fixed') {
      // Get thumbnail from first preroll in the list
      if (block.preroll_ids && block.preroll_ids.length > 0) {
        const firstPreroll = prerolls.find((p) => p.id === block.preroll_ids[0]);
        return firstPreroll?.thumbnail;
      }
      return null;
    } else if (block.type === 'random' || block.type === 'sequential') {
      const categoryPrerolls = prerolls.filter((p) => p.category_id === block.category_id);
      return categoryPrerolls[0]?.thumbnail;
    }
    return null;
  };

  // Get icon component for block type
  const getBlockIcon = (type, size = 20) => {
    const iconProps = { size, strokeWidth: 2 };
    const icons = {
      preroll: <Film {...iconProps} />,
      fixed: <ListOrdered {...iconProps} />,
      random: <Shuffle {...iconProps} />,
      sequential: <Play {...iconProps} />,
      queue: <Layers {...iconProps} />,
      sequence: <Clapperboard {...iconProps} />,
      separator: <GripVertical {...iconProps} />,
    };
    return icons[type] || <Film {...iconProps} />;
  };

  // Get display label for block type
  const getBlockLabel = (type) => {
    const labels = {
      preroll: 'Single',
      fixed: 'Fixed',
      random: 'Random',
      sequential: 'Sequential',
      queue: 'Queue',
      sequence: 'Sequence',
      separator: 'Divider',
    };
    return labels[type] || type;
  };

  if (blocks.length === 0) {
    return (
      <div
        style={{
          padding: '2.5rem',
          textAlign: 'center',
          backgroundColor: 'var(--card-bg)',
          borderRadius: '12px',
          border: '2px dashed var(--border-color)',
        }}
      >
        <div style={{ marginBottom: '1rem', opacity: 0.5 }}>
          <BarChart3 size={48} strokeWidth={1.5} />
        </div>
        <p style={{ fontSize: '1rem', color: 'var(--text-secondary)', margin: 0 }}>
          No blocks in sequence yet. Add blocks above to see the timeline.
        </p>
      </div>
    );
  }

  return (
    <div
      style={{
        backgroundColor: 'var(--card-bg)',
        borderRadius: '12px',
        padding: '1.25rem',
        border: '1px solid var(--border-color)',
        boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
      }}
    >
      {/* Timeline Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '1rem',
          paddingBottom: '0.75rem',
          borderBottom: '1px solid var(--border-color)',
          flexWrap: 'wrap',
          gap: '0.75rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <BarChart3 size={20} style={{ color: '#6366f1' }} />
          <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600, color: 'var(--text-color)' }}>
            Sequence Timeline
          </h3>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', fontSize: '0.8rem', flexWrap: 'wrap' }}>
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '0.3rem',
            padding: '0.3rem 0.6rem',
            backgroundColor: 'rgba(99, 102, 241, 0.1)',
            borderRadius: '6px',
            color: '#6366f1',
            fontWeight: 600
          }}>
            <Layers size={13} />
            {blocks.length} block{blocks.length !== 1 ? 's' : ''}
          </div>
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '0.3rem',
            padding: '0.3rem 0.6rem',
            backgroundColor: 'rgba(16, 185, 129, 0.1)',
            borderRadius: '6px',
            color: '#10b981',
            fontWeight: 600
          }}>
            <Film size={13} />
            {totalPrerolls} preroll{totalPrerolls !== 1 ? 's' : ''}
          </div>
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '0.3rem',
            padding: '0.3rem 0.6rem',
            backgroundColor: 'rgba(245, 158, 11, 0.1)',
            borderRadius: '6px',
            color: '#f59e0b',
            fontWeight: 600
          }}>
            <Timer size={13} />
            {formatDuration(totalDuration)}
          </div>
        </div>
      </div>

      {/* Timeline Blocks */}
      <div
        style={{
          display: 'flex',
          gap: '0.5rem',
          overflowX: 'auto',
          paddingBottom: '0.75rem',
          paddingTop: '0.25rem',
        }}
      >
        {blocksWithDurations.map((block, index) => {
          const widthPercentage = totalDuration > 0 ? (block.duration / totalDuration) * 100 : 100 / blocks.length;
          const minWidth = block.type === 'separator' ? '4px' : '100px';
          const colors = getBlockColor(block.type);
          const thumbnail = getThumbnail(block);

          if (block.type === 'separator') {
            return (
              <div
                key={block.id || index}
                style={{
                  flex: '0 0 4px',
                  minWidth: '4px',
                  maxWidth: '4px',
                  backgroundColor: '#6b7280',
                  borderRadius: '2px',
                  alignSelf: 'stretch',
                }}
              />
            );
          }

          return (
            <div
              key={block.id || index}
              onClick={() => onBlockClick && onBlockClick(block, index)}
              style={{
                flex: `0 0 ${Math.max(widthPercentage, 10)}%`,
                minWidth,
                maxWidth: '200px',
                background: colors.bg,
                borderRadius: '10px',
                padding: '0.75rem',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                border: '2px solid transparent',
                position: 'relative',
                overflow: 'hidden',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-3px) scale(1.02)';
                e.currentTarget.style.boxShadow = '0 8px 20px rgba(0,0,0,0.25)';
                e.currentTarget.style.borderColor = 'rgba(255,255,255,0.3)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0) scale(1)';
                e.currentTarget.style.boxShadow = 'none';
                e.currentTarget.style.borderColor = 'transparent';
              }}
            >
              {/* Block Number Badge */}
              <div
                style={{
                  position: 'absolute',
                  top: '0.5rem',
                  left: '0.5rem',
                  backgroundColor: 'rgba(0,0,0,0.4)',
                  backdropFilter: 'blur(4px)',
                  borderRadius: '6px',
                  width: '22px',
                  height: '22px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.7rem',
                  fontWeight: 700,
                  color: 'white',
                }}
              >
                {index + 1}
              </div>

              {/* Duration Badge */}
              <div
                style={{
                  position: 'absolute',
                  top: '0.5rem',
                  right: '0.5rem',
                  backgroundColor: 'rgba(0,0,0,0.4)',
                  backdropFilter: 'blur(4px)',
                  borderRadius: '6px',
                  padding: '0.15rem 0.35rem',
                  fontSize: '0.6rem',
                  fontWeight: 600,
                  color: 'white',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.15rem',
                }}
              >
                <Clock size={9} />
                {formatDuration(block.duration)}
              </div>

              {/* Thumbnail (if available) */}
              {thumbnail && (
                <div
                  style={{
                    width: '100%',
                    height: '45px',
                    borderRadius: '6px',
                    overflow: 'hidden',
                    marginTop: '1.5rem',
                    marginBottom: '0.5rem',
                    backgroundColor: 'rgba(0,0,0,0.2)',
                  }}
                >
                  <img
                    src={thumbnail}
                    alt={getCategoryName(block)}
                    style={{
                      width: '100%',
                      height: '100%',
                      objectFit: 'cover',
                    }}
                    onError={(e) => {
                      e.target.style.display = 'none';
                    }}
                  />
                </div>
              )}

              {/* Block Info */}
              <div style={{ 
                textAlign: 'center', 
                color: 'white',
                marginTop: thumbnail ? '0' : '1.75rem',
              }}>
                <div style={{ 
                  marginBottom: '0.3rem',
                  display: 'flex',
                  justifyContent: 'center',
                  opacity: 0.95,
                }}>
                  {getBlockIcon(block.type, 20)}
                </div>
                <div
                  style={{
                    fontSize: '0.65rem',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                    marginBottom: '0.2rem',
                    opacity: 0.85,
                  }}
                >
                  {getBlockLabel(block.type)}
                </div>
                <div
                  style={{
                    fontSize: '0.7rem',
                    opacity: 0.9,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    fontWeight: 500,
                  }}
                  title={getCategoryName(block)}
                >
                  {getCategoryName(block)}
                </div>
                {/* Show count for random blocks */}
                {block.type === 'random' && block.count > 1 && (
                  <div style={{
                    fontSize: '0.6rem',
                    marginTop: '0.2rem',
                    opacity: 0.7,
                    fontWeight: 600,
                  }}>
                    × {block.count} random
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Timeline Legend */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '0.5rem',
          marginTop: '0.75rem',
          paddingTop: '0.75rem',
          borderTop: '1px solid var(--border-color)',
          justifyContent: 'center',
        }}
      >
        {[
          { type: 'fixed', label: 'Fixed Order' },
          { type: 'random', label: 'Random Pick' },
          { type: 'sequential', label: 'Sequential' },
        ].map(({ type, label }) => (
          <div 
            key={type} 
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '0.35rem',
              padding: '0.25rem 0.5rem',
              backgroundColor: 'var(--bg-color)',
              borderRadius: '6px',
              fontSize: '0.7rem',
            }}
          >
            <div
              style={{
                width: '14px',
                height: '14px',
                borderRadius: '4px',
                background: getBlockColor(type).bg,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {React.cloneElement(getBlockIcon(type, 9), { color: 'white' })}
            </div>
            <span style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>
              {label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default SequenceTimeline;
