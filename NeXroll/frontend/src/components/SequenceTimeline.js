import React from 'react';

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

  // Format duration as MM:SS
  const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Get block color based on type
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

  // Get icon for block type
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

  if (blocks.length === 0) {
    return (
      <div
        style={{
          padding: '2rem',
          textAlign: 'center',
          backgroundColor: 'var(--card-bg)',
          borderRadius: '0.5rem',
          border: '2px dashed var(--border-color)',
        }}
      >
        <p style={{ fontSize: '1.1rem', color: '#9ca3af' }}>
          🎬 No blocks in sequence yet. Add blocks above to see timeline.
        </p>
      </div>
    );
  }

  return (
    <div
      style={{
        backgroundColor: 'var(--card-bg)',
        borderRadius: '0.5rem',
        padding: '1.5rem',
        border: '1px solid var(--border-color)',
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
          borderBottom: '2px solid var(--border-color)',
        }}
      >
        <h3 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--text-color)' }}>
          📊 Sequence Timeline
        </h3>
        <div style={{ fontSize: '0.95rem', color: '#9ca3af' }}>
          <strong>Total Duration:</strong> {formatDuration(totalDuration)} ({Math.ceil(totalDuration / 60)} min)
        </div>
      </div>

      {/* Timeline Blocks */}
      <div
        style={{
          display: 'flex',
          gap: '0.5rem',
          overflowX: 'auto',
          paddingBottom: '1rem',
        }}
      >
        {blocksWithDurations.map((block, index) => {
          const widthPercentage = (block.duration / totalDuration) * 100;
          const minWidth = block.type === 'separator' ? '2px' : '80px';

          return (
            <div
              key={block.id || index}
              onClick={() => onBlockClick && onBlockClick(block, index)}
              style={{
                flex: `0 0 ${widthPercentage}%`,
                minWidth,
                maxWidth: block.type === 'separator' ? '4px' : 'none',
                backgroundColor: getBlockColor(block.type),
                borderRadius: '0.5rem',
                padding: block.type === 'separator' ? '0' : '0.75rem',
                cursor: 'pointer',
                transition: 'all 0.2s',
                border: '2px solid transparent',
                position: 'relative',
                overflow: 'hidden',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-4px)';
                e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.2)';
                e.currentTarget.style.borderColor = '#00d4ff';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = 'none';
                e.currentTarget.style.borderColor = 'transparent';
              }}
            >
              {block.type !== 'separator' && (
                <>
                  {/* Block Number */}
                  <div
                    style={{
                      position: 'absolute',
                      top: '0.25rem',
                      left: '0.25rem',
                      backgroundColor: 'rgba(0,0,0,0.5)',
                      borderRadius: '50%',
                      width: '24px',
                      height: '24px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '0.75rem',
                      fontWeight: 'bold',
                      color: 'white',
                    }}
                  >
                    {index + 1}
                  </div>

                  {/* Thumbnail (if available) */}
                  {getThumbnail(block) && (
                    <div
                      style={{
                        width: '100%',
                        height: '60px',
                        borderRadius: '0.25rem',
                        overflow: 'hidden',
                        marginBottom: '0.5rem',
                        backgroundColor: 'rgba(0,0,0,0.2)',
                      }}
                    >
                      <img
                        src={getThumbnail(block)}
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
                  <div style={{ textAlign: 'center', color: 'white' }}>
                    <div style={{ fontSize: '1.5rem', marginBottom: '0.25rem' }}>
                      {getBlockIcon(block.type)}
                    </div>
                    <div
                      style={{
                        fontSize: '0.7rem',
                        fontWeight: 'bold',
                        textTransform: 'uppercase',
                        marginBottom: '0.25rem',
                        opacity: 0.9,
                      }}
                    >
                      {block.type}
                    </div>
                    <div
                      style={{
                        fontSize: '0.75rem',
                        opacity: 0.85,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                      title={getCategoryName(block)}
                    >
                      {getCategoryName(block)}
                    </div>
                    <div
                      style={{
                        fontSize: '0.7rem',
                        marginTop: '0.25rem',
                        opacity: 0.7,
                        fontWeight: 'bold',
                      }}
                    >
                      {formatDuration(block.duration)}
                    </div>
                  </div>
                </>
              )}
            </div>
          );
        })}
      </div>

      {/* Timeline Legend */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '1rem',
          marginTop: '1rem',
          paddingTop: '0.75rem',
          borderTop: '1px solid var(--border-color)',
          fontSize: '0.85rem',
        }}
      >
        {[
          { type: 'preroll', label: 'Single Preroll' },
          { type: 'random', label: 'Random Selection' },
          { type: 'sequential', label: 'Sequential Play' },
          { type: 'queue', label: 'Queue Items' },
          { type: 'sequence', label: 'Nested Sequence' },
          { type: 'separator', label: 'Divider' },
        ].map(({ type, label }) => (
          <div key={type} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <div
              style={{
                width: '16px',
                height: '16px',
                borderRadius: '0.25rem',
                backgroundColor: getBlockColor(type),
              }}
            />
            <span style={{ color: '#9ca3af' }}>
              {getBlockIcon(type)} {label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default SequenceTimeline;
