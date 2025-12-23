import React from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Edit, Copy, Trash2, ChevronUp, ChevronDown, Shuffle, ListOrdered, Film, Pin, Tag, Link } from 'lucide-react';

/**
 * SequenceBlock - Individual block in the sequence (random or fixed)
 * Supports drag-and-drop reordering
 */
const SequenceBlock = ({
  block,
  index,
  getCategoryName,
  getPrerollNames,
  onEdit,
  onDelete,
  onMoveUp,
  onMoveDown,
  onDuplicate,
  isFirst,
  isLast,
}) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: block.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const renderBlockContent = () => {
    // Handle different block types
    const blockType = block.type;
    
    if (blockType === 'random') {
      const categoryName = getCategoryName(block.category_id);
      const count = block.count || 1;
      return (
        <>
          <div style={{
            minWidth: '48px',
            height: '48px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            boxShadow: '0 2px 8px rgba(102, 126, 234, 0.3)'
          }}>
            <Shuffle size={24} color="white" />
          </div>
          <div style={{ flex: 1 }}>
            {block.label && (
              <div style={{
                fontSize: '13px',
                fontWeight: 600,
                color: 'var(--accent-color)',
                marginBottom: '8px',
                padding: '4px 10px',
                background: 'var(--hover-bg)',
                borderRadius: '4px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                border: '1px solid var(--accent-color)'
              }}>
                <Tag size={14} />
                {block.label}
              </div>
            )}
            <div style={{
              fontWeight: 'bold',
              fontSize: '16px',
              color: 'var(--text-color)',
              marginBottom: '8px'
            }}>Random Block</div>
            <div style={{
              fontSize: '14px',
              color: 'var(--text-secondary)',
              marginBottom: '5px'
            }}>
              <strong style={{ color: 'var(--text-color)' }}>Category:</strong> {categoryName}
            </div>
            <div style={{
              fontSize: '14px',
              color: 'var(--text-secondary)',
              marginBottom: '5px'
            }}>
              <strong style={{ color: 'var(--text-color)' }}>Count:</strong> {count} {count === 1 ? 'preroll' : 'prerolls'}
            </div>
          </div>
        </>
      );
    } else if (blockType === 'sequential') {
      const categoryName = getCategoryName(block.category_id);
      const count = block.count || 1;
      return (
        <>
          <div style={{
            minWidth: '48px',
            height: '48px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
            boxShadow: '0 2px 8px rgba(240, 147, 251, 0.3)'
          }}>
            <ListOrdered size={24} color="white" />
          </div>
          <div style={{ flex: 1 }}>
            {block.label && (
              <div style={{
                fontSize: '13px',
                fontWeight: 600,
                color: 'var(--accent-color)',
                marginBottom: '8px',
                padding: '4px 10px',
                background: 'var(--hover-bg)',
                borderRadius: '4px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                border: '1px solid var(--accent-color)'
              }}>
                <Tag size={14} />
                {block.label}
              </div>
            )}
            <div style={{
              fontWeight: 'bold',
              fontSize: '16px',
              color: 'var(--text-color)',
              marginBottom: '8px'
            }}>Sequential Block</div>
            <div style={{
              fontSize: '14px',
              color: 'var(--text-secondary)',
              marginBottom: '5px'
            }}>
              <strong style={{ color: 'var(--text-color)' }}>Category:</strong> {categoryName}
            </div>
            <div style={{
              fontSize: '14px',
              color: 'var(--text-secondary)',
              marginBottom: '5px'
            }}>
              <strong style={{ color: 'var(--text-color)' }}>Count:</strong> {count} {count === 1 ? 'preroll' : 'prerolls'}
            </div>
          </div>
        </>
      );
    } else if (blockType === 'preroll') {
      // Single preroll block - support old format with preroll_id
      const prerollId = block.preroll_id;
      const prerollNames = getPrerollNames([prerollId]);
      const prerollName = prerollNames.length > 0 ? prerollNames[0] : 'Unknown';
      return (
        <>
          <div style={{
            minWidth: '48px',
            height: '48px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
            boxShadow: '0 2px 8px rgba(79, 172, 254, 0.3)'
          }}>
            <Film size={24} color="white" />
          </div>
          <div style={{ flex: 1 }}>
            {block.label && (
              <div style={{
                fontSize: '13px',
                fontWeight: 600,
                color: 'var(--accent-color)',
                marginBottom: '8px',
                padding: '4px 10px',
                background: 'var(--hover-bg)',
                borderRadius: '4px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                border: '1px solid var(--accent-color)'
              }}>
                <Tag size={14} />
                {block.label}
              </div>
            )}
            <div style={{
              fontWeight: 'bold',
              fontSize: '16px',
              color: 'var(--text-color)',
              marginBottom: '8px'
            }}>Single Preroll</div>
            <div style={{
              fontSize: '14px',
              color: 'var(--text-color)',
              fontWeight: 500,
              padding: '8px',
              background: 'var(--hover-bg)',
              borderRadius: '6px',
              border: '1px solid var(--border-color)'
            }}>
              {prerollName}
            </div>
          </div>
        </>
      );
    } else if (blockType === 'fixed') {
      // Fixed block - list of specific prerolls
      const prerollNames = getPrerollNames(block.preroll_ids || []);
      return (
        <>
          <div style={{
            minWidth: '48px',
            height: '48px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
            boxShadow: '0 2px 8px rgba(250, 112, 154, 0.3)'
          }}>
            <Pin size={24} color="white" />
          </div>
          <div style={{ flex: 1 }}>
            {block.label && (
              <div style={{
                fontSize: '13px',
                fontWeight: 600,
                color: 'var(--accent-color)',
                marginBottom: '8px',
                padding: '4px 10px',
                background: 'var(--hover-bg)',
                borderRadius: '4px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                border: '1px solid var(--accent-color)'
              }}>
                <Tag size={14} />
                {block.label}
              </div>
            )}
            <div style={{
              fontWeight: 'bold',
              fontSize: '16px',
              color: 'var(--text-color)',
              marginBottom: '8px'
            }}>Fixed Block</div>
            <div style={{
              fontSize: '14px',
              color: 'var(--text-secondary)',
              marginBottom: '5px'
            }}>
              <strong style={{ color: 'var(--text-color)' }}>Prerolls:</strong> {prerollNames.length === 0 ? 'None selected' : ''}
            </div>
            {prerollNames.length > 0 && (
              <div style={{
                marginTop: '10px',
                padding: '8px',
                background: 'var(--hover-bg)',
                borderRadius: '6px',
                border: '1px solid var(--border-color)'
              }}>
                {prerollNames.map((name, i) => (
                  <div key={i} style={{
                    fontSize: '14px',
                    color: 'var(--text-color)',
                    fontWeight: 500,
                    padding: '6px 10px',
                    borderLeft: '3px solid var(--accent-color)',
                    background: 'var(--hover-bg)',
                    borderRadius: '4px',
                    marginBottom: i === prerollNames.length - 1 ? 0 : '6px'
                  }}>
                    {i + 1}. {name}
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      );
    } else if (blockType === 'queue') {
      return (
        <>
          <div style={{
            fontSize: '32px',
            minWidth: '40px',
            textAlign: 'center'
          }}>⏭️</div>
          <div style={{ flex: 1 }}>
            <div style={{
              fontWeight: 'bold',
              fontSize: '16px',
              color: 'var(--text-color)',
              marginBottom: '8px'
            }}>Queue Block</div>
            <div style={{
              fontSize: '14px',
              color: 'var(--text-secondary)'
            }}>Plays next item from queue</div>
          </div>
        </>
      );
    } else if (blockType === 'sequence') {
      return (
        <>
          <div style={{
            minWidth: '48px',
            height: '48px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
            boxShadow: '0 2px 8px rgba(67, 233, 123, 0.3)'
          }}>
            <Link size={24} color="white" />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{
              fontWeight: 'bold',
              fontSize: '16px',
              color: 'var(--text-color)',
              marginBottom: '8px'
            }}>Nested Sequence</div>
            <div style={{
              fontSize: '14px',
              color: 'var(--text-secondary)'
            }}>Sequence ID: {block.sequence_id || 'Unknown'}</div>
          </div>
        </>
      );
    }
    return null;
  };

  return (
    <div
      ref={setNodeRef}
      style={{
        ...style,
        background: 'var(--card-bg)',
        border: '2px solid var(--border-color)',
        borderRadius: '8px',
        padding: '15px',
        transition: 'all 0.3s',
        cursor: 'default',
        opacity: isDragging ? 0.5 : 1,
      }}
      onMouseEnter={(e) => {
        if (!isDragging) {
          e.currentTarget.style.borderColor = 'var(--accent-color)';
          e.currentTarget.style.boxShadow = '0 4px 12px rgba(102, 126, 234, 0.2)';
        }
      }}
      onMouseLeave={(e) => {
        if (!isDragging) {
          e.currentTarget.style.borderColor = 'var(--border-color)';
          e.currentTarget.style.boxShadow = 'none';
        }
      }}
    >
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '15px',
        paddingBottom: '10px',
        borderBottom: '1px solid var(--border-color)',
      }}>
        <div style={{
          fontWeight: 'bold',
          color: 'var(--accent-color)',
          fontSize: '14px',
        }}>Block {index + 1}</div>
        <div 
          style={{
            cursor: 'grab',
            fontSize: '20px',
            color: 'var(--text-secondary)',
            padding: '5px 10px',
            userSelect: 'none',
          }}
          {...attributes} 
          {...listeners}
        >
          ⋮⋮
        </div>
      </div>

      <div style={{
        display: 'flex',
        gap: '15px',
        alignItems: 'flex-start',
        marginBottom: '15px',
      }}>
        {renderBlockContent()}
      </div>

      <div style={{
        display: 'flex',
        gap: '6px',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginTop: '4px',
      }}>
        {/* Move buttons grouped on left */}
        <div style={{ display: 'flex', gap: '4px' }}>
          <button
            type="button"
            style={{
              padding: '6px',
              fontSize: '11px',
              border: 'none',
              borderRadius: '6px',
              cursor: isFirst ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s',
              background: 'var(--button-secondary-bg)',
              color: 'var(--button-text)',
              opacity: isFirst ? 0.3 : 1,
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '32px',
              height: '32px',
            }}
            onClick={onMoveUp}
            disabled={isFirst}
            title="Move up"
          >
            <ChevronUp size={16} />
          </button>
          <button
            type="button"
            style={{
              padding: '6px',
              fontSize: '11px',
              border: 'none',
              borderRadius: '6px',
              cursor: isLast ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s',
              background: 'var(--button-secondary-bg)',
              color: 'var(--button-text)',
              opacity: isLast ? 0.3 : 1,
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '32px',
              height: '32px',
            }}
            onClick={onMoveDown}
            disabled={isLast}
            title="Move down"
          >
            <ChevronDown size={16} />
          </button>
        </div>
        
        {/* Action buttons grouped on right */}
        <div style={{ display: 'flex', gap: '6px' }}>
          <button
            type="button"
            style={{
              padding: '6px 12px',
              fontSize: '12px',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              transition: 'all 0.2s',
              background: 'var(--button-bg)',
              color: 'white',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
            onClick={onEdit}
            title="Edit block"
          >
            <Edit size={14} />
            Edit
          </button>
          <button
            type="button"
            style={{
              padding: '6px 12px',
              fontSize: '12px',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              transition: 'all 0.2s',
              background: '#48bb78',
              color: 'white',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
            onClick={onDuplicate}
            title="Duplicate block"
          >
            <Copy size={14} />
            Copy
          </button>
          <button
            type="button"
            style={{
              padding: '6px',
              fontSize: '11px',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              transition: 'all 0.2s',
              background: '#f56565',
              color: 'white',
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '32px',
              height: '32px',
            }}
            onClick={onDelete}
            title="Delete block"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>
    </div>
  );
};

export default SequenceBlock;
