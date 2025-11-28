import React from 'react';

/**
 * SequenceStats - Statistics dashboard for sequence analysis
 * Shows total duration, preroll count, block breakdown with visual charts
 * 
 * Props:
 * - blocks: Array of sequence blocks
 * - categories: Array of available categories
 * - prerolls: Array of all prerolls
 * - compact: Boolean - if true, show condensed version
 */
const SequenceStats = ({ blocks = [], categories = [], prerolls = [], compact = false }) => {
  // Calculate block statistics
  const calculateStats = () => {
    const stats = {
      totalBlocks: blocks.length,
      blockTypes: {},
      totalDuration: 0,
      estimatedPrerollCount: 0,
      categories: new Set(),
      prerollIds: new Set(),
    };

    blocks.forEach((block) => {
      // Count block types
      stats.blockTypes[block.type] = (stats.blockTypes[block.type] || 0) + 1;

      // Calculate duration and preroll count
      if (block.type === 'preroll') {
        const preroll = prerolls.find((p) => p.id === block.preroll_id);
        stats.totalDuration += preroll?.duration || 30;
        stats.estimatedPrerollCount += 1;
        stats.prerollIds.add(block.preroll_id);
      } else if (block.type === 'fixed') {
        // Fixed block - sum durations of specific prerolls
        if (block.preroll_ids && block.preroll_ids.length > 0) {
          block.preroll_ids.forEach(id => {
            const preroll = prerolls.find((p) => p.id === id);
            stats.totalDuration += preroll?.duration || 30;
            stats.prerollIds.add(id);
          });
          stats.estimatedPrerollCount += block.preroll_ids.length;
        }
      } else if (block.type === 'random') {
        const categoryPrerolls = prerolls.filter((p) => p.category_id === block.category_id);
        const avgDuration = categoryPrerolls.reduce((sum, p) => sum + (p.duration || 30), 0) / (categoryPrerolls.length || 1);
        stats.totalDuration += avgDuration * (block.count || 1);
        stats.estimatedPrerollCount += block.count || 1;
        stats.categories.add(block.category_id);
      } else if (block.type === 'sequential') {
        const categoryPrerolls = prerolls.filter((p) => p.category_id === block.category_id);
        stats.totalDuration += categoryPrerolls.reduce((sum, p) => sum + (p.duration || 30), 0);
        stats.estimatedPrerollCount += categoryPrerolls.length;
        stats.categories.add(block.category_id);
      } else if (block.type === 'queue') {
        stats.totalDuration += 90; // Estimate 3 items at 30s each
        stats.estimatedPrerollCount += 3;
      } else if (block.type === 'sequence') {
        stats.totalDuration += 120; // Estimate 2 min for nested sequence
        stats.estimatedPrerollCount += 4;
      }
      // Separator has 0 duration
    });

    return {
      ...stats,
      categoriesUsed: stats.categories.size,
      uniquePrerolls: stats.prerollIds.size,
    };
  };

  const stats = calculateStats();

  // Format duration as HH:MM:SS
  const formatDuration = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hours > 0) {
      return `${hours}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Get color for block type
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

  // Get friendly label for block type
  const getBlockLabel = (type) => {
    const labels = {
      preroll: 'Single Preroll',
      random: 'Random Selection',
      sequential: 'Sequential Play',
      queue: 'Queue Items',
      sequence: 'Nested Sequence',
      separator: 'Divider',
    };
    return labels[type] || type;
  };

  if (blocks.length === 0) {
    return (
      <div
        style={{
          padding: compact ? '1rem' : '1.5rem',
          textAlign: 'center',
          backgroundColor: 'var(--card-bg)',
          borderRadius: '0.5rem',
          border: '2px dashed var(--border-color)',
        }}
      >
        <p style={{ fontSize: '0.95rem', color: '#9ca3af', margin: 0 }}>
          📊 No statistics available. Add blocks to see stats.
        </p>
      </div>
    );
  }

  if (compact) {
    // Compact view for smaller spaces
    return (
      <div
        style={{
          backgroundColor: 'var(--card-bg)',
          borderRadius: '0.5rem',
          padding: '1rem',
          border: '1px solid var(--border-color)',
        }}
      >
        <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#667eea' }}>
              {formatDuration(stats.totalDuration)}
            </div>
            <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '0.25rem' }}>Total Duration</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#f59e0b' }}>
              {stats.estimatedPrerollCount}
            </div>
            <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '0.25rem' }}>Prerolls</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#10b981' }}>
              {stats.totalBlocks}
            </div>
            <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '0.25rem' }}>Blocks</div>
          </div>
        </div>
      </div>
    );
  }

  // Full dashboard view
  return (
    <div
      style={{
        backgroundColor: 'var(--card-bg)',
        borderRadius: '0.5rem',
        padding: '1.5rem',
        border: '1px solid var(--border-color)',
      }}
    >
      {/* Header */}
      <h3 style={{ margin: 0, marginBottom: '1.5rem', fontSize: '1.1rem', color: 'var(--text-color)' }}>
        📊 Sequence Statistics
      </h3>

      {/* Main Stats Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
          gap: '1rem',
          marginBottom: '1.5rem',
        }}
      >
        {/* Total Duration */}
        <div
          style={{
            backgroundColor: 'rgba(102, 126, 234, 0.1)',
            borderRadius: '0.5rem',
            padding: '1rem',
            border: '2px solid rgba(102, 126, 234, 0.3)',
          }}
        >
          <div style={{ fontSize: '0.8rem', color: '#9ca3af', marginBottom: '0.5rem', textTransform: 'uppercase' }}>
            ⏱️ Total Duration
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: '#667eea' }}>
            {formatDuration(stats.totalDuration)}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '0.25rem' }}>
            ({Math.ceil(stats.totalDuration / 60)} minutes)
          </div>
        </div>

        {/* Preroll Count */}
        <div
          style={{
            backgroundColor: 'rgba(245, 158, 11, 0.1)',
            borderRadius: '0.5rem',
            padding: '1rem',
            border: '2px solid rgba(245, 158, 11, 0.3)',
          }}
        >
          <div style={{ fontSize: '0.8rem', color: '#9ca3af', marginBottom: '0.5rem', textTransform: 'uppercase' }}>
            🎬 Est. Prerolls
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: '#f59e0b' }}>
            {stats.estimatedPrerollCount}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '0.25rem' }}>
            {stats.uniquePrerolls > 0 && `${stats.uniquePrerolls} unique`}
          </div>
        </div>

        {/* Block Count */}
        <div
          style={{
            backgroundColor: 'rgba(16, 185, 129, 0.1)',
            borderRadius: '0.5rem',
            padding: '1rem',
            border: '2px solid rgba(16, 185, 129, 0.3)',
          }}
        >
          <div style={{ fontSize: '0.8rem', color: '#9ca3af', marginBottom: '0.5rem', textTransform: 'uppercase' }}>
            🔢 Total Blocks
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: '#10b981' }}>
            {stats.totalBlocks}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '0.25rem' }}>
            {stats.categoriesUsed > 0 && `${stats.categoriesUsed} categories`}
          </div>
        </div>
      </div>

      {/* Block Type Breakdown */}
      <div
        style={{
          marginTop: '1.5rem',
          paddingTop: '1.5rem',
          borderTop: '1px solid var(--border-color)',
        }}
      >
        <h4 style={{ margin: 0, marginBottom: '1rem', fontSize: '0.95rem', color: 'var(--text-color)' }}>
          Block Type Breakdown
        </h4>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {Object.entries(stats.blockTypes)
            .sort(([, a], [, b]) => b - a) // Sort by count descending
            .map(([type, count]) => {
              const percentage = (count / stats.totalBlocks) * 100;
              return (
                <div key={type}>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: '0.25rem',
                      fontSize: '0.85rem',
                    }}
                  >
                    <span style={{ color: 'var(--text-color)' }}>
                      {getBlockIcon(type)} {getBlockLabel(type)}
                    </span>
                    <span style={{ color: '#9ca3af', fontWeight: 'bold' }}>
                      {count} ({percentage.toFixed(0)}%)
                    </span>
                  </div>
                  <div
                    style={{
                      width: '100%',
                      height: '8px',
                      backgroundColor: 'rgba(156, 163, 175, 0.2)',
                      borderRadius: '4px',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        width: `${percentage}%`,
                        height: '100%',
                        backgroundColor: getBlockColor(type),
                        transition: 'width 0.3s ease',
                      }}
                    />
                  </div>
                </div>
              );
            })}
        </div>
      </div>

      {/* Quick Insights */}
      <div
        style={{
          marginTop: '1.5rem',
          paddingTop: '1.5rem',
          borderTop: '1px solid var(--border-color)',
        }}
      >
        <h4 style={{ margin: 0, marginBottom: '0.75rem', fontSize: '0.95rem', color: 'var(--text-color)' }}>
          💡 Quick Insights
        </h4>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.85rem', color: '#9ca3af' }}>
          {stats.totalDuration > 600 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>⚠️</span>
              <span>Long sequence (&gt;10 min) - users may skip prerolls</span>
            </div>
          )}
          {stats.totalDuration < 60 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>⚡</span>
              <span>Quick sequence (&lt;1 min) - great for fast-paced viewing</span>
            </div>
          )}
          {stats.blockTypes.random && stats.blockTypes.random > 2 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>🎲</span>
              <span>Lots of randomization - sequence will vary each playback</span>
            </div>
          )}
          {stats.blockTypes.preroll && stats.totalBlocks === stats.blockTypes.preroll && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>🎯</span>
              <span>Fixed sequence - plays identically every time</span>
            </div>
          )}
          {stats.categoriesUsed > 5 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>🌈</span>
              <span>Diverse sequence using {stats.categoriesUsed} different categories</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SequenceStats;
