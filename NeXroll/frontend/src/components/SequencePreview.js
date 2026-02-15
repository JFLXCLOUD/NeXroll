import React, { useMemo } from 'react';

/**
 * SequencePreview - Visual preview of the sequence structure
 * Shows estimated runtime, block order, and playback flow
 */
const SequencePreview = ({ blocks, categories, prerolls, getCategoryName, getPrerollNames }) => {
  const sequenceStats = useMemo(() => {
    let totalFixed = 0;
    let totalRandom = 0;
    let estimatedMin = 0;
    let estimatedMax = 0;
    const avgPrerollDuration = 30; // seconds (fallback if duration not available)

    blocks.forEach((block) => {
      if (block.type === 'random') {
        const count = block.count || 1;
        totalRandom += count;
        // Estimate based on average preroll duration
        estimatedMin += count * avgPrerollDuration;
        estimatedMax += count * avgPrerollDuration;
      } else if (block.type === 'fixed') {
        const prerollIds = block.preroll_ids || [];
        totalFixed += prerollIds.length;
        // Try to get actual durations
        prerollIds.forEach((id) => {
          const preroll = prerolls.find((p) => p.id === id);
          const duration = preroll?.duration || avgPrerollDuration;
          estimatedMin += duration;
          estimatedMax += duration;
        });
      }
    });

    const minMinutes = Math.floor(estimatedMin / 60);
    const maxMinutes = Math.ceil(estimatedMax / 60);

    return {
      totalBlocks: blocks.length,
      totalFixed,
      totalRandom,
      estimatedMin,
      estimatedMax,
      minMinutes,
      maxMinutes,
    };
  }, [blocks, prerolls]);

  // eslint-disable-next-line no-unused-vars
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div style={{
      background: 'var(--card-bg)',
      border: '2px solid var(--accent-color)',
      borderRadius: '12px',
      padding: '20px',
      marginBottom: '20px',
      boxShadow: '0 8px 24px rgba(102, 126, 234, 0.2)',
      animation: 'slideDown 0.3s ease-out'
    }}>
      <div style={{ marginBottom: '20px' }}>
        <h3 style={{
          margin: '0 0 15px 0',
          color: 'var(--accent-color)',
          fontSize: '20px',
          display: 'flex',
          alignItems: 'center',
          gap: '10px'
        }}>📺 Sequence Preview</h3>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
          gap: '15px'
        }}>
          <div style={{
            background: 'var(--hover-bg)',
            padding: '12px',
            borderRadius: '8px',
            textAlign: 'center'
          }}>
            <span style={{
              display: 'block',
              fontSize: '12px',
              color: 'var(--text-secondary)',
              marginBottom: '5px'
            }}>Total Blocks:</span>
            <span style={{
              display: 'block',
              fontSize: '20px',
              fontWeight: 'bold',
              color: 'var(--accent-color)'
            }}>{sequenceStats.totalBlocks}</span>
          </div>
          <div style={{
            background: 'var(--hover-bg)',
            padding: '12px',
            borderRadius: '8px',
            textAlign: 'center'
          }}>
            <span style={{
              display: 'block',
              fontSize: '12px',
              color: 'var(--text-secondary)',
              marginBottom: '5px'
            }}>Fixed Prerolls:</span>
            <span style={{
              display: 'block',
              fontSize: '20px',
              fontWeight: 'bold',
              color: 'var(--accent-color)'
            }}>{sequenceStats.totalFixed}</span>
          </div>
          <div style={{
            background: 'var(--hover-bg)',
            padding: '12px',
            borderRadius: '8px',
            textAlign: 'center'
          }}>
            <span style={{
              display: 'block',
              fontSize: '12px',
              color: 'var(--text-secondary)',
              marginBottom: '5px'
            }}>Random Selections:</span>
            <span style={{
              display: 'block',
              fontSize: '20px',
              fontWeight: 'bold',
              color: 'var(--accent-color)'
            }}>{sequenceStats.totalRandom}</span>
          </div>
          <div style={{
            background: 'var(--hover-bg)',
            padding: '12px',
            borderRadius: '8px',
            textAlign: 'center'
          }}>
            <span style={{
              display: 'block',
              fontSize: '12px',
              color: 'var(--text-secondary)',
              marginBottom: '5px'
            }}>Est. Runtime:</span>
            <span style={{
              display: 'block',
              fontSize: '20px',
              fontWeight: 'bold',
              color: 'var(--accent-color)'
            }}>
              {sequenceStats.minMinutes === sequenceStats.maxMinutes
                ? `${sequenceStats.minMinutes} min`
                : `${sequenceStats.minMinutes}-${sequenceStats.maxMinutes} min`}
            </span>
          </div>
        </div>
      </div>

      <div style={{ marginTop: '20px' }}>
        <h4 style={{
          color: 'var(--accent-color)',
          marginBottom: '15px',
          fontSize: '18px'
        }}>Playback Order</h4>
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '15px',
          position: 'relative',
          paddingLeft: '40px'
        }}>
          {blocks.map((block, index) => {
            const isRandom = block.type === 'random';
            const isFixed = block.type === 'fixed';

            return (
              <div key={index} style={{
                display: 'flex',
                alignItems: 'flex-start',
                position: 'relative'
              }}>
                <div style={{
                  position: 'absolute',
                  left: '-40px',
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  background: 'var(--accent-color)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontWeight: 'bold',
                  color: '#000',
                  zIndex: 2
                }}>
                  <span>{index + 1}</span>
                </div>
                <div style={{
                  flex: 1,
                  background: block.type === 'random' 
                    ? 'linear-gradient(135deg, rgba(255, 193, 7, 0.1), rgba(255, 152, 0, 0.1))'
                    : 'linear-gradient(135deg, rgba(33, 150, 243, 0.1), rgba(21, 101, 192, 0.1))',
                  border: `2px solid ${block.type === 'random' ? '#ffc107' : '#2196f3'}`,
                  borderRadius: '12px',
                  padding: '15px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '15px'
                }}>
                  {isRandom && (
                    <>
                      <div style={{
                        fontSize: '32px',
                        lineHeight: 1
                      }}>🎲</div>
                      <div style={{ flex: 1 }}>
                        <strong style={{ 
                          display: 'block',
                          color: 'var(--text-color)',
                          marginBottom: '5px'
                        }}>Random Block</strong>
                        <p style={{
                          margin: '5px 0',
                          color: 'var(--text-color)'
                        }}>{getCategoryName(block.category_id)}</p>
                        <small style={{
                          color: 'var(--text-secondary)',
                          fontSize: '13px'
                        }}>Will randomly select {block.count} {block.count === 1 ? 'preroll' : 'prerolls'}</small>
                      </div>
                    </>
                  )}
                  {isFixed && (
                    <>
                      <div style={{
                        fontSize: '32px',
                        lineHeight: 1
                      }}>📌</div>
                      <div style={{ flex: 1 }}>
                        <strong style={{
                          display: 'block',
                          color: 'var(--text-color)',
                          marginBottom: '8px'
                        }}>Fixed Block</strong>
                        <div style={{
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '5px'
                        }}>
                          {getPrerollNames(block.preroll_ids || []).map((name, i) => (
                            <div key={i} style={{
                              padding: '6px 10px',
                              background: 'var(--hover-bg)',
                              borderRadius: '6px',
                              fontSize: '13px',
                              color: 'var(--text-color)'
                            }}>
                              {i + 1}. {name}
                            </div>
                          ))}
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <div style={{
          marginTop: '25px',
          padding: '20px',
          background: 'var(--hover-bg)',
          borderRadius: '12px',
          borderLeft: '4px solid var(--accent-color)'
        }}>
          <p style={{
            margin: '0 0 15px 0',
            color: 'var(--text-color)',
            lineHeight: '1.6'
          }}>
            <strong>💡 How it works:</strong> When this sequence is triggered, blocks execute in order from top to bottom. 
            Random blocks pick prerolls randomly each time, while fixed blocks always play the same prerolls in the specified order.
          </p>
        </div>
      </div>
    </div>
  );
};

export default SequencePreview;
