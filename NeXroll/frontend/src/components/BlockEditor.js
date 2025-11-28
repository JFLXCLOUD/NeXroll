import React, { useState, useEffect } from 'react';

/**
 * BlockEditor - Modal for configuring sequence blocks
 * Supports both random and fixed block types
 */
const BlockEditor = ({ block, categories, prerolls, isNew, onSave, onCancel }) => {
  const [blockType, setBlockType] = useState(block.type || 'random');
  const [categoryId, setCategoryId] = useState(block.category_id || (categories[0]?.id || null));
  const [count, setCount] = useState(block.count || 1);
  const [selectedPrerollIds, setSelectedPrerollIds] = useState(block.preroll_ids || []);
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedCategories, setExpandedCategories] = useState({});
  const [label, setLabel] = useState(block.label || '');

  useEffect(() => {
    setBlockType(block.type || 'random');
    setCategoryId(block.category_id || (categories[0]?.id || null));
    setCount(block.count || 1);
    setSelectedPrerollIds(block.preroll_ids || []);
    setLabel(block.label || '');
  }, [block, categories]);

  const handleSave = () => {
    const newBlock = {
      ...block,
      type: blockType,
      label: label.trim() || undefined, // Only save if not empty
    };

    if (blockType === 'random') {
      newBlock.category_id = categoryId;
      newBlock.count = count;
      // Remove fixed block properties
      delete newBlock.preroll_ids;
    } else {
      newBlock.preroll_ids = selectedPrerollIds;
      // Remove random block properties
      delete newBlock.category_id;
      delete newBlock.count;
    }

    onSave(newBlock);
  };

  const togglePrerollSelection = (prerollId) => {
    setSelectedPrerollIds((prev) => {
      if (prev.includes(prerollId)) {
        return prev.filter((id) => id !== prerollId);
      } else {
        return [...prev, prerollId];
      }
    });
  };

  const movePrerollUp = (index) => {
    if (index > 0) {
      setSelectedPrerollIds((prev) => {
        const newList = [...prev];
        [newList[index - 1], newList[index]] = [newList[index], newList[index - 1]];
        return newList;
      });
    }
  };

  const movePrerollDown = (index) => {
    if (index < selectedPrerollIds.length - 1) {
      setSelectedPrerollIds((prev) => {
        const newList = [...prev];
        [newList[index], newList[index + 1]] = [newList[index + 1], newList[index]];
        return newList;
      });
    }
  };

  const removePreroll = (prerollId) => {
    setSelectedPrerollIds((prev) => prev.filter((id) => id !== prerollId));
  };

  const getPreroll = (id) => prerolls.find((p) => p.id === id);
  
  const getCategoryPrerollCount = (catId) => {
    return prerolls.filter((p) => 
      p.category_id === catId || (p.categories && p.categories.some(c => c.id === catId))
    ).length;
  };

  const filteredPrerolls = prerolls.filter((p) => {
    const name = (p.display_name || p.filename || '').toLowerCase();
    return name.includes(searchTerm.toLowerCase());
  });

  // Group prerolls by category
  const prerollsByCategory = {};
  filteredPrerolls.forEach((preroll) => {
    const catId = preroll.category_id || 0;
    if (!prerollsByCategory[catId]) {
      prerollsByCategory[catId] = [];
    }
    prerollsByCategory[catId].push(preroll);
  });

  const toggleCategory = (catId) => {
    setExpandedCategories(prev => ({
      ...prev,
      [catId]: !prev[catId]
    }));
  };

  const canSave = blockType === 'random' 
    ? (categoryId !== null && count > 0)
    : (selectedPrerollIds.length > 0);

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0, 0, 0, 0.8)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      animation: 'fadeIn 0.2s'
    }} onClick={onCancel}>
      <div style={{
        background: 'var(--card-bg)',
        borderRadius: '12px',
        width: '90%',
        maxWidth: '700px',
        maxHeight: '90vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 20px 60px rgba(0, 0, 0, 0.6)',
        animation: 'slideUp 0.3s',
        border: '1px solid var(--border-color)'
      }} onClick={(e) => e.stopPropagation()}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '20px',
          borderBottom: '2px solid var(--border-color)'
        }}>
          <h2 style={{
            margin: 0,
            color: 'var(--accent-color)',
            fontSize: '22px'
          }}>{isNew ? 'Add New Block' : 'Edit Block'}</h2>
          <button type="button" style={{
            background: 'none',
            border: 'none',
            fontSize: '24px',
            color: 'var(--text-secondary)',
            cursor: 'pointer',
            padding: '5px 10px',
            transition: 'color 0.2s'
          }} onClick={onCancel}>✖</button>
        </div>

        <div style={{
          padding: '20px',
          overflowY: 'auto',
          flex: 1
        }}>
          {/* Block Label (Custom Name) */}
          <div style={{ marginBottom: '20px' }}>
            <label htmlFor="block-label" style={{
              display: 'block',
              marginBottom: '8px',
              color: 'var(--text-color)',
              fontWeight: 600,
              fontSize: '14px'
            }}>Block Label (Optional)</label>
            <input
              id="block-label"
              type="text"
              placeholder="e.g., 'Opening Credits', 'Holiday Special', 'Action Pack'"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              style={{
                width: '100%',
                padding: '10px',
                border: '2px solid var(--border-color)',
                borderRadius: '6px',
                background: 'var(--input-bg)',
                color: 'var(--text-color)',
                fontSize: '14px',
                transition: 'border-color 0.3s',
                boxSizing: 'border-box'
              }}
            />
            <small style={{ 
              display: 'block', 
              marginTop: '6px', 
              color: 'var(--text-secondary)', 
              fontSize: '12px' 
            }}>
              Give this block a custom name to help identify it in your sequence
            </small>
          </div>

          {/* Block Type Selection */}
          <div style={{ marginBottom: '20px' }}>
            <label style={{
              display: 'block',
              marginBottom: '8px',
              color: 'var(--text-color)',
              fontWeight: 600,
              fontSize: '14px'
            }}>Block Type</label>
            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '15px'
            }}>
              <button
                type="button"
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  padding: '20px',
                  border: blockType === 'random' ? '2px solid var(--accent-color)' : '2px solid var(--border-color)',
                  borderRadius: '8px',
                  background: blockType === 'random' ? 'var(--hover-bg)' : 'var(--card-bg)',
                  color: 'var(--text-color)',
                  cursor: 'pointer',
                  transition: 'all 0.3s'
                }}
                onClick={() => setBlockType('random')}
              >
                <span style={{ fontSize: '32px', marginBottom: '10px' }}>🎲</span>
                <span style={{ fontWeight: 'bold', fontSize: '16px', marginBottom: '5px' }}>Random</span>
                <small style={{ fontSize: '11px', color: 'var(--text-secondary)', textAlign: 'center' }}>Select random prerolls from a category</small>
              </button>
              <button
                type="button"
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  padding: '20px',
                  border: blockType === 'fixed' ? '2px solid var(--accent-color)' : '2px solid var(--border-color)',
                  borderRadius: '8px',
                  background: blockType === 'fixed' ? 'var(--hover-bg)' : 'var(--card-bg)',
                  color: 'var(--text-color)',
                  cursor: 'pointer',
                  transition: 'all 0.3s'
                }}
                onClick={() => setBlockType('fixed')}
              >
                <span style={{ fontSize: '32px', marginBottom: '10px' }}>📌</span>
                <span style={{ fontWeight: 'bold', fontSize: '16px', marginBottom: '5px' }}>Fixed</span>
                <small style={{ fontSize: '11px', color: 'var(--text-secondary)', textAlign: 'center' }}>Specific prerolls in order</small>
              </button>
            </div>
          </div>

          {/* Random Block Configuration */}
          {blockType === 'random' && (
            <>
              <div style={{ marginBottom: '20px' }}>
                <label htmlFor="category-select" style={{
                  display: 'block',
                  marginBottom: '8px',
                  color: 'var(--text-color)',
                  fontWeight: 600,
                  fontSize: '14px'
                }}>Category</label>
                <select
                  id="category-select"
                  value={categoryId || ''}
                  onChange={(e) => setCategoryId(parseInt(e.target.value))}
                  style={{
                    width: '100%',
                    padding: '10px',
                    border: '2px solid var(--border-color)',
                    borderRadius: '6px',
                    background: 'var(--input-bg)',
                    color: 'var(--text-color)',
                    fontSize: '14px',
                    transition: 'border-color 0.3s',
                    cursor: 'pointer'
                  }}
                >
                  {categories.map((cat) => (
                    <option 
                      key={cat.id} 
                      value={cat.id}
                      style={{
                        background: 'var(--input-bg)',
                        color: 'var(--text-color)',
                        padding: '10px'
                      }}
                    >
                      {cat.name} ({getCategoryPrerollCount(cat.id)} prerolls)
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ marginBottom: '20px' }}>
                <label htmlFor="count-input" style={{
                  display: 'block',
                  marginBottom: '8px',
                  color: 'var(--text-color)',
                  fontWeight: 600,
                  fontSize: '14px'
                }}>Number of Random Prerolls</label>
                <input
                  id="count-input"
                  type="number"
                  min="1"
                  max="10"
                  value={count}
                  onChange={(e) => setCount(parseInt(e.target.value) || 1)}
                  style={{
                    width: '100%',
                    padding: '10px',
                    border: '2px solid var(--border-color)',
                    borderRadius: '6px',
                    background: 'var(--input-bg)',
                    color: 'var(--text-color)',
                    fontSize: '14px',
                    transition: 'border-color 0.3s'
                  }}
                />
                <small style={{
                  display: 'block',
                  marginTop: '5px',
                  color: 'var(--text-secondary)',
                  fontSize: '12px'
                }}>
                  Will randomly select {count} {count === 1 ? 'preroll' : 'prerolls'} from this category
                </small>
              </div>

              {categoryId && (
                <div style={{
                  background: 'var(--hover-bg)',
                  border: '1px solid var(--accent-color)',
                  borderRadius: '6px',
                  padding: '15px',
                  marginTop: '10px'
                }}>
                  <strong style={{
                    color: 'var(--accent-color)',
                    display: 'block',
                    marginBottom: '8px'
                  }}>Preview:</strong>
                  <p style={{
                    margin: '5px 0',
                    color: 'var(--text-color)',
                    fontSize: '13px'
                  }}>✓ {getCategoryPrerollCount(categoryId)} prerolls available</p>
                  <p style={{
                    margin: '5px 0',
                    color: 'var(--text-color)',
                    fontSize: '13px'
                  }}>✓ Will randomly select {count} on each playback</p>
                </div>
              )}
            </>
          )}

          {/* Fixed Block Configuration */}
          {blockType === 'fixed' && (
            <>
              <div className="form-group">
                <label>Selected Prerolls (Order Matters)</label>
                {selectedPrerollIds.length === 0 ? (
                  <div className="empty-selection">
                    No prerolls selected. Choose from the list below.
                  </div>
                ) : (
                  <div className="selected-prerolls">
                    {selectedPrerollIds.map((id, index) => {
                      const preroll = getPreroll(id);
                      if (!preroll) return null;
                      return (
                        <div key={id} className="selected-preroll-item">
                          <span className="order-number">{index + 1}.</span>
                          <span className="preroll-name">
                            {preroll.display_name || preroll.filename}
                          </span>
                          <div className="item-actions">
                            <button
                              type="button"
                              className="btn-icon"
                              onClick={() => movePrerollUp(index)}
                              disabled={index === 0}
                              title="Move up"
                            >
                              ↑
                            </button>
                            <button
                              type="button"
                              className="btn-icon"
                              onClick={() => movePrerollDown(index)}
                              disabled={index === selectedPrerollIds.length - 1}
                              title="Move down"
                            >
                              ↓
                            </button>
                            <button
                              type="button"
                              className="btn-icon btn-remove"
                              onClick={() => removePreroll(id)}
                              title="Remove"
                            >
                              ✖
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              <div style={{ marginBottom: '20px' }}>
                <label style={{
                  display: 'block',
                  marginBottom: '8px',
                  color: 'var(--text-color)',
                  fontWeight: 600,
                  fontSize: '14px'
                }}>Available Prerolls</label>
                <input
                  type="text"
                  placeholder="Search prerolls..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px',
                    border: '2px solid var(--border-color)',
                    borderRadius: '6px',
                    background: 'var(--input-bg)',
                    color: 'var(--text-color)',
                    fontSize: '14px',
                    marginBottom: '10px'
                  }}
                />
                <div style={{
                  border: '2px solid var(--border-color)',
                  borderRadius: '6px',
                  background: 'var(--card-bg)',
                  maxHeight: '300px',
                  overflowY: 'auto'
                }}>
                  {Object.keys(prerollsByCategory).length === 0 ? (
                    <div style={{
                      padding: '30px',
                      textAlign: 'center',
                      color: 'var(--text-secondary)',
                      fontSize: '14px'
                    }}>No prerolls found</div>
                  ) : (
                    Object.keys(prerollsByCategory).map((catId) => {
                      const category = categories.find(c => c.id === parseInt(catId));
                      const categoryPrerolls = prerollsByCategory[catId];
                      const isExpanded = expandedCategories[catId];
                      
                      return (
                        <div key={catId}>
                          <div
                            onClick={() => toggleCategory(catId)}
                            style={{
                              padding: '12px',
                              background: 'var(--hover-bg)',
                              borderBottom: '1px solid var(--border-color)',
                              cursor: 'pointer',
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                              fontWeight: 600,
                              color: 'var(--text-color)'
                            }}
                          >
                            <span>{isExpanded ? '▼' : '▶'} {category ? category.name : 'Uncategorized'} ({categoryPrerolls.length})</span>
                          </div>
                          {isExpanded && categoryPrerolls.map((preroll) => {
                            const isSelected = selectedPrerollIds.includes(preroll.id);
                            return (
                              <div
                                key={preroll.id}
                                onClick={() => togglePrerollSelection(preroll.id)}
                                style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '10px',
                                  padding: '12px 12px 12px 30px',
                                  borderBottom: '1px solid var(--border-color)',
                                  cursor: 'pointer',
                                  background: isSelected ? 'var(--hover-bg)' : 'transparent',
                                  transition: 'background 0.2s'
                                }}
                              >
                                <input
                                  type="checkbox"
                                  checked={isSelected}
                                  onClick={(e) => e.stopPropagation()}
                                  onChange={(e) => {
                                    e.stopPropagation();
                                    togglePrerollSelection(preroll.id);
                                  }}
                                  style={{ cursor: 'pointer' }}
                                />
                                <span style={{
                                  flex: 1,
                                  color: 'var(--text-color)',
                                  fontSize: '14px'
                                }}>
                                  {preroll.display_name || preroll.filename}
                                </span>
                                {isSelected && (
                                  <span style={{
                                    background: 'var(--accent-color)',
                                    color: 'white',
                                    padding: '2px 8px',
                                    borderRadius: '12px',
                                    fontSize: '11px',
                                    fontWeight: 'bold'
                                  }}>
                                    #{selectedPrerollIds.indexOf(preroll.id) + 1}
                                  </span>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            </>
          )}
        </div>

        <div style={{
          padding: '20px',
          borderTop: '2px solid var(--border-color)',
          display: 'flex',
          justifyContent: 'flex-end',
          gap: '10px'
        }}>
          <button type="button" style={{
            padding: '10px 24px',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: 600,
            transition: 'all 0.3s',
            background: 'var(--button-secondary-bg)',
            color: 'var(--button-text)'
          }} onClick={onCancel}>
            Cancel
          </button>
          <button 
            type="button"
            style={{
              padding: '10px 24px',
              border: 'none',
              borderRadius: '6px',
              cursor: canSave ? 'pointer' : 'not-allowed',
              fontSize: '14px',
              fontWeight: 600,
              transition: 'all 0.3s',
              background: 'var(--button-bg)',
              color: 'white',
              opacity: canSave ? 1 : 0.5
            }}
            onClick={handleSave}
            disabled={!canSave}
          >
            {isNew ? 'Add Block' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default BlockEditor;
