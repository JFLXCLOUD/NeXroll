import React, { useState, useEffect } from 'react';
import { DndContext, closestCenter, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy, arrayMove } from '@dnd-kit/sortable';
import { Download, Upload, Play, Save, Edit, Trash2, X, Film, Shuffle, Pin, LayoutGrid, BarChart3 } from 'lucide-react';
import SequenceBlock from './SequenceBlock';
import BlockEditor from './BlockEditor';
import SequencePreview from './SequencePreview';
import SequenceTimeline from './SequenceTimeline';
import SequenceStats from './SequenceStats';
import SequencePreviewModal from './SequencePreviewModal';
import PatternExport from './PatternExport';
import PatternImport from './PatternImport';

/**
 * SequenceBuilder - Visual preroll sequence builder for NeXroll
 * 
 * Allows users to create custom preroll sequences with:
 * - Random blocks (select N random prerolls from a category)
 * - Fixed blocks (specific prerolls in order)
 * - Drag-and-drop reordering
 * - Live preview with timeline visualization
 * - Statistics dashboard
 * - Full-screen preview modal with playback simulator
 * 
 * Integrates with NeXroll's existing scheduler. Sequences are stored in the
 * schedule's `sequence` field and processed by the backend scheduler.
 * 
 * Sequence JSON format:
 * [
 *   {"type": "random", "category_id": 5, "count": 2},
 *   {"type": "fixed", "preroll_ids": [12, 45, 67]},
 *   {"type": "random", "category_id": 8, "count": 1}
 * ]
 */
const SequenceBuilder = ({ blocks: externalBlocks = [], onBlocksChange, initialSequence = [], categories = [], prerolls = [], onSave, onCancel, onDelete, scheduleId = null, apiUrl, isEditing = false, initialName = '', initialDescription = '' }) => {
  // Use external blocks if provided, otherwise use internal state
  const [internalBlocks, setInternalBlocks] = useState([]);
  // Use external blocks if onBlocksChange callback is provided (controlled mode)
  const blocks = onBlocksChange ? externalBlocks : internalBlocks;
  const setBlocks = onBlocksChange || setInternalBlocks;
  
  const [editingBlock, setEditingBlock] = useState(null);
  const [editingIndex, setEditingIndex] = useState(null);
  const [showPreview, setShowPreview] = useState(false);
  const [isModified, setIsModified] = useState(false);
  const [viewMode, setViewMode] = useState('card'); // 'card' or 'timeline'
  const [showFullPreview, setShowFullPreview] = useState(false);
  const [showExportModal, setShowExportModal] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [sequenceName, setSequenceName] = useState(initialName);
  const [sequenceDescription, setSequenceDescription] = useState(initialDescription);
  
  // Update name and description when initial values change (e.g., when loading a sequence for editing)
  React.useEffect(() => {
    setSequenceName(initialName);
    setSequenceDescription(initialDescription);
  }, [initialName, initialDescription]);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    })
  );

  // Load initial sequence
  useEffect(() => {
    // Ensure initialSequence is an array
    const sequence = Array.isArray(initialSequence) ? initialSequence : [];
    if (sequence.length > 0) {
      // Add unique IDs for drag-and-drop
      const blocksWithIds = sequence.map((block, index) => ({
        ...block,
        id: `block-${Date.now()}-${index}`,
      }));
      setBlocks(blocksWithIds);
    }
  }, [initialSequence]);

  const handleDragEnd = (event) => {
    const { active, over } = event;

    if (active.id !== over?.id) {
      setBlocks((items) => {
        const oldIndex = items.findIndex((item) => item.id === active.id);
        const newIndex = items.findIndex((item) => item.id === over.id);
        const newBlocks = arrayMove(items, oldIndex, newIndex);
        setIsModified(true);
        return newBlocks;
      });
    }
  };

  const handleAddBlock = (type) => {
    const newBlock = {
      id: `block-${Date.now()}`,
      type: type,
      // Defaults
      ...(type === 'random' 
        ? { category_id: categories[0]?.id || null, count: 1 }
        : { preroll_ids: [] }
      )
    };
    setEditingBlock(newBlock);
    setEditingIndex(null); // null means adding new
  };

  const handleEditBlock = (block, index) => {
    setEditingBlock({ ...block });
    setEditingIndex(index);
  };

  const handleDeleteBlock = (index) => {
    setBlocks((items) => {
      const newBlocks = items.filter((_, i) => i !== index);
      setIsModified(true);
      return newBlocks;
    });
  };

  const handleMoveBlock = (index, direction) => {
    if (direction === 'up' && index > 0) {
      setBlocks((items) => {
        const newBlocks = arrayMove(items, index, index - 1);
        setIsModified(true);
        return newBlocks;
      });
    } else if (direction === 'down' && index < blocks.length - 1) {
      setBlocks((items) => {
        const newBlocks = arrayMove(items, index, index + 1);
        setIsModified(true);
        return newBlocks;
      });
    }
  };

  const handleSaveBlock = (block) => {
    if (editingIndex !== null) {
      // Update existing block
      setBlocks((items) => {
        const newBlocks = [...items];
        newBlocks[editingIndex] = { ...block, id: items[editingIndex].id };
        return newBlocks;
      });
    } else {
      // Add new block
      setBlocks((items) => [...items, block]);
    }
    setEditingBlock(null);
    setEditingIndex(null);
    setIsModified(true);
  };

  const handleCancelEdit = () => {
    setEditingBlock(null);
    setEditingIndex(null);
  };

  const handleSaveSequence = () => {
    if (!sequenceName.trim()) {
      alert('Please enter a sequence name');
      return;
    }
    // Strip IDs and labels before saving (backend doesn't need them)
    const cleanBlocks = blocks.map(({ id, label, ...block }) => block);
    onSave(sequenceName.trim(), sequenceDescription.trim());
  };

  const handleDuplicateBlock = (block, index) => {
    const duplicated = {
      ...block,
      id: `block-${Date.now()}-duplicate`,
    };
    setBlocks((items) => {
      const newBlocks = [...items];
      newBlocks.splice(index + 1, 0, duplicated);
      return newBlocks;
    });
    setIsModified(true);
  };

  const getCategoryName = (categoryId) => {
    const category = categories.find((c) => c.id === categoryId);
    return category ? category.name : 'Unknown Category';
  };

  const getPrerollNames = (prerollIds) => {
    if (!prerollIds || prerollIds.length === 0) return [];
    return prerollIds
      .map((id) => {
        const preroll = prerolls.find((p) => p.id === id);
        return preroll ? (preroll.display_name || preroll.filename) : null;
      })
      .filter(Boolean);
  };

  const handleImportPattern = (importedData) => {
    // importedData contains: { name, blocks, sequenceJson, matchResults }
    const importedBlocks = importedData.blocks || [];
    
    // Add unique IDs for drag-and-drop
    const blocksWithIds = importedBlocks.map((block, index) => ({
      ...block,
      id: `block-${Date.now()}-${index}`,
    }));
    setBlocks(blocksWithIds);
    setIsModified(true);
    setShowImportModal(false);
  };

  return (
    <div style={{
      padding: '20px',
      background: 'var(--card-bg)',
      borderRadius: '8px',
      color: 'var(--text-color)',
      border: '1px solid var(--border-color)'
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '20px',
        paddingBottom: '15px',
        borderBottom: '2px solid var(--border-color)'
      }}>
        <div>
          <h2 style={{
            margin: 0,
            color: 'var(--text-color)',
            fontSize: '24px'
          }}>Sequence Builder</h2>
          <p style={{
            margin: '5px 0 0 0',
            fontSize: '13px',
            color: 'var(--text-secondary)'
          }}>
            {blocks.length === 0 ? 'No blocks yet' : `${blocks.length} block${blocks.length === 1 ? '' : 's'}`}
          </p>
        </div>
        <div style={{
          display: 'flex',
          gap: '10px',
          alignItems: 'center'
        }}>
          {/* View Toggle */}
          {blocks.length > 0 && (
            <div style={{
              display: 'flex',
              gap: '0',
              backgroundColor: 'var(--hover-bg)',
              borderRadius: '5px',
              padding: '3px',
              border: '1px solid var(--border-color)'
            }}>
              <button
                type="button"
                onClick={() => setViewMode('card')}
                style={{
                  padding: '8px 16px',
                  border: 'none',
                  borderRadius: '3px',
                  cursor: 'pointer',
                  fontSize: '13px',
                  backgroundColor: viewMode === 'card' ? '#667eea' : 'transparent',
                  color: viewMode === 'card' ? 'white' : 'var(--text-color)',
                  transition: 'all 0.2s',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
              >
                <LayoutGrid size={14} /> Card
              </button>
              <button
                type="button"
                onClick={() => setViewMode('timeline')}
                style={{
                  padding: '8px 16px',
                  border: 'none',
                  borderRadius: '3px',
                  cursor: 'pointer',
                  fontSize: '13px',
                  backgroundColor: viewMode === 'timeline' ? '#667eea' : 'transparent',
                  color: viewMode === 'timeline' ? 'white' : 'var(--text-color)',
                  transition: 'all 0.2s',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
              >
                <BarChart3 size={14} /> Timeline
              </button>
            </div>
          )}
          
          {/* Export/Import Buttons */}
          {scheduleId && blocks.length > 0 && (
            <button 
              type="button"
              style={{
                padding: '10px 20px',
                border: 'none',
                borderRadius: '5px',
                cursor: 'pointer',
                fontSize: '14px',
                transition: 'all 0.3s',
                background: '#f59e0b',
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
              onClick={() => setShowExportModal(true)}
            >
              <Upload size={16} /> Export
            </button>
          )}
          
          {/* Hide Import button when editing a sequence */}
          {!isEditing && (
            <button 
              type="button"
              style={{
                padding: '10px 20px',
                border: 'none',
                borderRadius: '5px',
                cursor: 'pointer',
                fontSize: '14px',
                transition: 'all 0.3s',
                background: '#8b5cf6',
                color: 'white'
              }}
              onClick={() => setShowImportModal(true)}
            >
              <Download size={16} style={{ marginRight: '6px', verticalAlign: 'middle' }} />
              Import
            </button>
          )}
          
          {/* Full Preview Button */}
          <button 
            type="button"
            style={{
              padding: '10px 20px',
              border: 'none',
              borderRadius: '5px',
              cursor: blocks.length === 0 ? 'not-allowed' : 'pointer',
              fontSize: '14px',
              transition: 'all 0.3s',
              background: '#667eea',
              color: 'white',
              opacity: blocks.length === 0 ? 0.5 : 1,
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
            onClick={() => {
              console.log('Opening sequence playback modal, blocks:', blocks.length);
              setShowFullPreview(true);
            }}
            disabled={blocks.length === 0}
          >
            <Play size={16} />
            Play Sequence
          </button>
          
          <button 
            type="button"
            style={{
              padding: '10px 20px',
              border: 'none',
              borderRadius: '5px',
              cursor: (blocks.length === 0 || !sequenceName.trim()) ? 'not-allowed' : 'pointer',
              fontSize: '14px',
              transition: 'all 0.3s',
              background: '#28a745',
              color: 'white',
              opacity: (blocks.length === 0 || !sequenceName.trim()) ? 0.5 : 1,
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
            onClick={handleSaveSequence}
            disabled={blocks.length === 0 || !sequenceName.trim()}
            title={!sequenceName.trim() ? 'Please enter a sequence name' : (isEditing ? 'Update this sequence' : 'Save this sequence to your library')}
          >
            {isEditing ? (
              <>
                <Edit size={16} />
                Update Sequence
              </>
            ) : (
              <>
                <Save size={16} />
                Save & Add to Library
              </>
            )}
          </button>
          
          {/* Show Delete button only when editing an existing sequence */}
          {isEditing && onDelete && (
            <button 
              type="button"
              style={{
                padding: '10px 20px',
                border: 'none',
                borderRadius: '5px',
                cursor: 'pointer',
                fontSize: '14px',
                transition: 'all 0.3s',
                background: '#dc3545',
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
              onClick={() => {
                if (window.confirm(`Are you sure you want to delete "${sequenceName}"? This action cannot be undone.`)) {
                  onDelete();
                }
              }}
              title="Delete this sequence permanently"
            >
              <Trash2 size={16} />
              Delete Sequence
            </button>
          )}
          
          <button 
            type="button"
            style={{
              padding: '10px 20px',
              border: 'none',
              borderRadius: '5px',
              cursor: 'pointer',
              fontSize: '14px',
              transition: 'all 0.3s',
              background: 'var(--button-secondary-bg)',
              color: 'var(--button-text)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
            onClick={onCancel}
          >
            <X size={16} />
            Cancel
          </button>
        </div>
      </div>

      {/* Sequence Name and Description */}
      <div style={{
        marginBottom: '20px',
        padding: '15px',
        backgroundColor: 'var(--hover-bg)',
        borderRadius: '8px',
        border: '1px solid var(--border-color)'
      }}>
        <div style={{ marginBottom: '15px' }}>
          <label style={{
            display: 'block',
            marginBottom: '5px',
            fontWeight: '600',
            fontSize: '14px',
            color: 'var(--text-color)'
          }}>
            Sequence Name *
          </label>
          <input
            type="text"
            value={sequenceName}
            onChange={(e) => setSequenceName(e.target.value)}
            placeholder="Enter a name for this sequence..."
            style={{
              width: '100%',
              padding: '10px',
              fontSize: '14px',
              border: '1px solid var(--border-color)',
              borderRadius: '5px',
              backgroundColor: 'var(--bg-color)',
              color: 'var(--text-color)',
              boxSizing: 'border-box'
            }}
          />
        </div>
        <div>
          <label style={{
            display: 'block',
            marginBottom: '5px',
            fontWeight: '600',
            fontSize: '14px',
            color: 'var(--text-color)'
          }}>
            Description (Optional)
          </label>
          <textarea
            value={sequenceDescription}
            onChange={(e) => setSequenceDescription(e.target.value)}
            placeholder="Add a description for this sequence..."
            rows="3"
            style={{
              width: '100%',
              padding: '10px',
              fontSize: '14px',
              border: '1px solid var(--border-color)',
              borderRadius: '5px',
              backgroundColor: 'var(--bg-color)',
              color: 'var(--text-color)',
              boxSizing: 'border-box',
              resize: 'vertical'
            }}
          />
        </div>
      </div>

      {/* Compact Statistics (always visible when blocks exist) */}
      {blocks.length > 0 && (
        <div style={{ marginBottom: '20px' }}>
          <SequenceStats
            blocks={blocks}
            categories={categories}
            prerolls={prerolls}
            compact={true}
          />
        </div>
      )}

      {/* Timeline View (when selected and blocks exist) */}
      {viewMode === 'timeline' && blocks.length > 0 && (
        <div style={{ marginBottom: '20px' }}>
          <SequenceTimeline
            blocks={blocks}
            categories={categories}
            prerolls={prerolls}
            onBlockClick={(block, index) => handleEditBlock(block, index)}
          />
        </div>
      )}

      {/* Legacy Preview (keeping for backwards compatibility) */}
      {showPreview && blocks.length > 0 && (
        <SequencePreview 
          blocks={blocks}
          categories={categories}
          prerolls={prerolls}
          getCategoryName={getCategoryName}
          getPrerollNames={getPrerollNames}
        />
      )}

      {/* Card View / Drag-and-Drop Area */}
      {viewMode === 'card' && (
        <div style={{
          minHeight: '300px',
          background: 'var(--hover-bg)',
          border: '2px dashed var(--border-color)',
          borderRadius: '8px',
          padding: '20px',
          marginBottom: '20px'
        }}>
          {blocks.length === 0 ? (
          <div style={{
            textAlign: 'center',
            padding: '60px 20px',
            color: 'var(--text-secondary)'
          }}>
            <p style={{
              fontSize: '18px',
              margin: '10px 0',
              color: 'var(--text-color)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px'
            }}><Film size={20} /> No blocks yet. Add blocks to start building your sequence.</p>
            <p style={{
              fontSize: '14px',
              color: 'var(--text-secondary)',
              marginTop: '20px'
            }}>
              Create custom preroll sequences with random selections and fixed prerolls.
            </p>
          </div>
        ) : (
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
          >
            <SortableContext
              items={blocks.map((b) => b.id)}
              strategy={verticalListSortingStrategy}
            >
              <div style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '15px'
              }}>
                {blocks.map((block, index) => (
                  <SequenceBlock
                    key={block.id}
                    block={block}
                    index={index}
                    getCategoryName={getCategoryName}
                    getPrerollNames={getPrerollNames}
                    onEdit={() => handleEditBlock(block, index)}
                    onDelete={() => handleDeleteBlock(index)}
                    onMoveUp={() => handleMoveBlock(index, 'up')}
                    onMoveDown={() => handleMoveBlock(index, 'down')}
                    onDuplicate={() => handleDuplicateBlock(block, index)}
                    isFirst={index === 0}
                    isLast={index === blocks.length - 1}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        )}
        </div>
      )}

      <div style={{
        display: 'flex',
        gap: '15px',
        justifyContent: 'center',
        marginTop: '20px'
      }}>
        <button 
          type="button"
          style={{
            padding: '15px 30px',
            fontSize: '16px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            background: 'var(--button-bg)',
            border: 'none',
            color: 'white',
            borderRadius: '8px',
            cursor: 'pointer',
            transition: 'all 0.3s'
          }}
          onClick={() => handleAddBlock('random')}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'translateY(-2px)';
            e.currentTarget.style.boxShadow = '0 5px 15px rgba(102, 126, 234, 0.4)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'translateY(0)';
            e.currentTarget.style.boxShadow = 'none';
          }}
        >
          <Shuffle size={20} /> Add Random Block
        </button>
        <button 
          type="button"
          style={{
            padding: '15px 30px',
            fontSize: '16px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            background: 'var(--button-bg)',
            border: 'none',
            color: 'white',
            borderRadius: '8px',
            cursor: 'pointer',
            transition: 'all 0.3s'
          }}
          onClick={() => handleAddBlock('fixed')}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'translateY(-2px)';
            e.currentTarget.style.boxShadow = '0 5px 15px rgba(102, 126, 234, 0.4)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'translateY(0)';
            e.currentTarget.style.boxShadow = 'none';
          }}
        >
          <Pin size={20} /> Add Fixed Block
        </button>
      </div>

      {editingBlock && (
        <BlockEditor
          block={editingBlock}
          categories={categories}
          prerolls={prerolls}
          isNew={editingIndex === null}
          onSave={handleSaveBlock}
          onCancel={handleCancelEdit}
        />
      )}

      {/* Full-screen Preview Modal */}
      <SequencePreviewModal
        isOpen={showFullPreview}
        onClose={() => setShowFullPreview(false)}
        blocks={blocks}
        categories={categories}
        prerolls={prerolls}
        sequenceName="Current Sequence"
        apiUrl={apiUrl}
      />

      {/* Pattern Export Modal */}
      {scheduleId && (
        <PatternExport
          isOpen={showExportModal}
          onClose={() => setShowExportModal(false)}
          scheduleId={scheduleId}
        />
      )}

      {/* Pattern Import Modal */}
      <PatternImport
        isOpen={showImportModal}
        onClose={() => setShowImportModal(false)}
        onImport={handleImportPattern}
      />
    </div>
  );
};

export default SequenceBuilder;
