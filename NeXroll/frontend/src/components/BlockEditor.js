import React, { useState, useEffect } from 'react';
import { Shuffle, Pin, X, ChevronUp, ChevronDown, Search, Tag, Check, Film, LayoutGrid, Sparkles } from 'lucide-react';

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
  const [initialBlockId, setInitialBlockId] = useState(block.id);
  // NeX-Up Trailers state
  const [nexupSource, setNexupSource] = useState(block.source || 'both');
  const [nexupCount, setNexupCount] = useState(block.count || 2);
  // Coming Soon List state
  const [comingSoonLayout, setComingSoonLayout] = useState(block.layout || 'grid');
  // Dynamic Preroll state
  const [dpTemplate, setDpTemplate] = useState(block.template || '');
  const [dpTheme, setDpTheme] = useState(block.theme || '');
  const [dynamicPrerolls, setDynamicPrerolls] = useState([]);
  const [dynamicPrerollsLoading, setDynamicPrerollsLoading] = useState(false);

  // Only reset state when opening a different block (detected by ID change)
  useEffect(() => {
    if (block.id !== initialBlockId) {
      setBlockType(block.type || 'random');
      setCategoryId(block.category_id || (categories[0]?.id || null));
      setCount(block.count || 1);
      setSelectedPrerollIds(block.preroll_ids || []);
      setLabel(block.label || '');
      setInitialBlockId(block.id);
      setNexupSource(block.source || 'both');
      setNexupCount(block.count || 2);
      setComingSoonLayout(block.layout || 'grid');
      setDpTemplate(block.template || '');
      setDpTheme(block.theme || '');
    }
  }, [block.id, block, categories, initialBlockId]);

  // Fetch dynamic preroll list when that block type is selected
  useEffect(() => {
    if (blockType === 'dynamic_preroll' && dynamicPrerolls.length === 0 && !dynamicPrerollsLoading) {
      setDynamicPrerollsLoading(true);
      fetch('/nexup/preroll/list')
        .then(res => res.json())
        .then(data => {
          setDynamicPrerolls(data.prerolls || []);
          // Auto-select first if no template/theme set
          if (!dpTemplate && data.prerolls && data.prerolls.length > 0) {
            const first = data.prerolls[0].template_id || '';
            const parts = first.split('_');
            if (parts.length >= 2) {
              const theme = parts[parts.length - 1];
              const template = parts.slice(0, -1).join('_');
              setDpTemplate(template);
              setDpTheme(theme);
            }
          }
        })
        .catch(() => setDynamicPrerolls([]))
        .finally(() => setDynamicPrerollsLoading(false));
    }
  }, [blockType, dynamicPrerolls.length, dynamicPrerollsLoading, dpTemplate]);

  const handleSave = () => {
    const newBlock = {
      ...block,
      type: blockType,
      label: label.trim() || undefined, // Only save if not empty
    };

    if (blockType === 'random') {
      newBlock.category_id = categoryId;
      newBlock.count = count;
      delete newBlock.preroll_ids;
      delete newBlock.source;
      delete newBlock.layout;
      delete newBlock.template;
      delete newBlock.theme;
    } else if (blockType === 'fixed') {
      newBlock.preroll_ids = selectedPrerollIds;
      delete newBlock.category_id;
      delete newBlock.count;
      delete newBlock.source;
      delete newBlock.layout;
      delete newBlock.template;
      delete newBlock.theme;
    } else if (blockType === 'nexup_trailers') {
      newBlock.source = nexupSource;
      newBlock.count = nexupCount;
      delete newBlock.category_id;
      delete newBlock.preroll_ids;
      delete newBlock.layout;
      delete newBlock.template;
      delete newBlock.theme;
    } else if (blockType === 'coming_soon_list') {
      newBlock.layout = comingSoonLayout;
      delete newBlock.category_id;
      delete newBlock.count;
      delete newBlock.preroll_ids;
      delete newBlock.source;
      delete newBlock.template;
      delete newBlock.theme;
    } else if (blockType === 'dynamic_preroll') {
      newBlock.template = dpTemplate;
      newBlock.theme = dpTheme;
      delete newBlock.category_id;
      delete newBlock.count;
      delete newBlock.preroll_ids;
      delete newBlock.source;
      delete newBlock.layout;
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
    : blockType === 'fixed'
    ? (selectedPrerollIds.length > 0)
    : blockType === 'nexup_trailers'
    ? (nexupCount > 0)
    : blockType === 'coming_soon_list'
    ? true
    : blockType === 'dynamic_preroll'
    ? (dpTemplate && dpTheme)
    : false;

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
        width: '95%',
        maxWidth: '850px',
        maxHeight: '85vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 20px 60px rgba(0, 0, 0, 0.6)',
        animation: 'slideUp 0.3s',
        border: '1px solid var(--border-color)',
        overflow: 'hidden'
      }} onClick={(e) => e.stopPropagation()}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '16px 20px',
          borderBottom: '2px solid var(--border-color)',
          background: 'var(--hover-bg)'
        }}>
          <h2 style={{
            margin: 0,
            color: 'var(--text-color)',
            fontSize: '20px',
            fontWeight: 700
          }}>{isNew ? 'Add New Block' : 'Edit Block'}</h2>
          <button type="button" style={{
            background: 'none',
            border: 'none',
            color: 'var(--text-secondary)',
            cursor: 'pointer',
            padding: '5px',
            transition: 'color 0.2s',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }} onClick={onCancel}>
            <X size={20} />
          </button>
        </div>

        <div style={{
          padding: '20px',
          overflowY: 'auto',
          flex: 1
        }}>
          {/* Block Label (Custom Name) */}
          <div style={{ marginBottom: '16px' }}>
            <label htmlFor="block-label" style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              marginBottom: '8px',
              color: 'var(--text-color)',
              fontWeight: 600,
              fontSize: '13px'
            }}>
              <Tag size={16} />
              Block Label (Optional)
            </label>
            <input
              id="block-label"
              type="text"
              placeholder="e.g., 'Opening Credits', 'Holiday Special'"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              style={{
                width: '100%',
                padding: '9px 12px',
                border: '2px solid var(--border-color)',
                borderRadius: '6px',
                background: 'var(--input-bg)',
                color: 'var(--text-color)',
                fontSize: '13px',
                transition: 'border-color 0.3s',
                boxSizing: 'border-box'
              }}
            />
            <small style={{ 
              display: 'block', 
              marginTop: '5px', 
              color: 'var(--text-secondary)', 
              fontSize: '11px' 
            }}>
              Custom name to identify this block
            </small>
          </div>

          {/* Block Type Selection */}
          <div style={{ marginBottom: '16px' }}>
            <label style={{
              display: 'block',
              marginBottom: '8px',
              color: 'var(--text-color)',
              fontWeight: 600,
              fontSize: '13px'
            }}>Block Type</label>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
              gap: '10px'
            }}>
              {[
                { key: 'random', label: 'Random', desc: 'Random prerolls from category', icon: Shuffle, gradient: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', bgActive: 'linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%)', shadow: 'rgba(102, 126, 234, 0.2)' },
                { key: 'fixed', label: 'Fixed', desc: 'Specific prerolls in order', icon: Pin, gradient: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)', bgActive: 'linear-gradient(135deg, rgba(250, 112, 154, 0.1) 0%, rgba(254, 225, 64, 0.1) 100%)', shadow: 'rgba(250, 112, 154, 0.2)' },
                { key: 'nexup_trailers', label: 'NeX-Up Trailers', desc: 'Coming soon movie/TV trailers', icon: Film, gradient: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)', bgActive: 'linear-gradient(135deg, rgba(240, 147, 251, 0.1) 0%, rgba(245, 87, 108, 0.1) 100%)', shadow: 'rgba(240, 147, 251, 0.2)' },
                { key: 'coming_soon_list', label: 'Coming Soon List', desc: 'Generated coming soon video', icon: LayoutGrid, gradient: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)', bgActive: 'linear-gradient(135deg, rgba(79, 172, 254, 0.1) 0%, rgba(0, 242, 254, 0.1) 100%)', shadow: 'rgba(79, 172, 254, 0.2)' },
                { key: 'dynamic_preroll', label: 'Dynamic Preroll', desc: 'Themed generated preroll', icon: Sparkles, gradient: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)', bgActive: 'linear-gradient(135deg, rgba(67, 233, 123, 0.1) 0%, rgba(56, 249, 215, 0.1) 100%)', shadow: 'rgba(67, 233, 123, 0.2)' },
              ].map(({ key, label: typeLabel, desc, icon: Icon, gradient, bgActive, shadow }) => (
                <button
                  key={key}
                  type="button"
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    padding: '14px 10px',
                    border: blockType === key ? '2px solid var(--accent-color)' : '2px solid var(--border-color)',
                    borderRadius: '8px',
                    background: blockType === key ? bgActive : 'var(--card-bg)',
                    color: 'var(--text-color)',
                    cursor: 'pointer',
                    transition: 'all 0.3s',
                    boxShadow: blockType === key ? `0 2px 8px ${shadow}` : 'none'
                  }}
                  onClick={() => setBlockType(key)}
                >
                  <div style={{
                    width: '40px',
                    height: '40px',
                    borderRadius: '8px',
                    background: gradient,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginBottom: '8px'
                  }}>
                    <Icon size={20} color="white" />
                  </div>
                  <span style={{ fontWeight: 'bold', fontSize: '13px', marginBottom: '3px' }}>{typeLabel}</span>
                  <small style={{ fontSize: '10px', color: 'var(--text-secondary)', textAlign: 'center', lineHeight: '1.3' }}>{desc}</small>
                </button>
              ))}
            </div>
          </div>

          {/* Random Block Configuration */}
          {blockType === 'random' && (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '12px', marginBottom: '12px' }}>
                <div>
                  <label htmlFor="category-select" style={{
                    display: 'block',
                    marginBottom: '6px',
                    color: 'var(--text-color)',
                    fontWeight: 600,
                    fontSize: '13px'
                  }}>Category</label>
                  <select
                    id="category-select"
                    value={categoryId || ''}
                    onChange={(e) => setCategoryId(parseInt(e.target.value))}
                    style={{
                      width: '100%',
                      padding: '9px 12px',
                      border: '2px solid var(--border-color)',
                      borderRadius: '6px',
                      background: 'var(--input-bg)',
                      color: 'var(--text-color)',
                      fontSize: '13px',
                      transition: 'border-color 0.3s',
                      cursor: 'pointer'
                    }}
                  >
                    {[...categories].sort((a, b) => a.name.localeCompare(b.name)).map((cat) => (
                      <option 
                        key={cat.id} 
                        value={cat.id}
                        style={{
                          background: 'var(--input-bg)',
                          color: 'var(--text-color)'
                        }}
                      >
                        {cat.name} ({getCategoryPrerollCount(cat.id)})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label htmlFor="count-input" style={{
                    display: 'block',
                    marginBottom: '6px',
                    color: 'var(--text-color)',
                    fontWeight: 600,
                    fontSize: '13px'
                  }}>Count</label>
                  <input
                    id="count-input"
                    type="number"
                    min="1"
                    max="10"
                    value={count}
                    onChange={(e) => setCount(parseInt(e.target.value) || 1)}
                    style={{
                      width: '20%',
                      padding: '9px 12px',
                      border: '2px solid var(--border-color)',
                      borderRadius: '6px',
                      background: 'var(--input-bg)',
                      color: 'var(--text-color)',
                      fontSize: '13px',
                      transition: 'border-color 0.3s',
                      textAlign: 'center'
                    }}
                  />
                </div>
              </div>

              {categoryId && (
                <div style={{
                  background: 'var(--hover-bg)',
                  border: '1px solid var(--accent-color)',
                  borderRadius: '6px',
                  padding: '10px 12px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  fontSize: '12px'
                }}>
                  <Check size={16} color="var(--accent-color)" />
                  <span style={{ color: 'var(--text-color)' }}>
                    {getCategoryPrerollCount(categoryId)} available • Will select {count} random on each playback
                  </span>
                </div>
              )}
            </>
          )}

          {/* Fixed Block Configuration */}
          {blockType === 'fixed' && (
            <>
              {selectedPrerollIds.length > 0 && (
                <div style={{ marginBottom: '12px' }}>
                  <label style={{
                    display: 'block',
                    marginBottom: '6px',
                    color: 'var(--text-color)',
                    fontWeight: 600,
                    fontSize: '13px'
                  }}>Selected ({selectedPrerollIds.length})</label>
                  <div style={{
                    border: '2px solid var(--border-color)',
                    borderRadius: '6px',
                    background: 'var(--card-bg)',
                    maxHeight: '140px',
                    overflowY: 'auto'
                  }}>
                    {selectedPrerollIds.map((id, index) => {
                      const preroll = getPreroll(id);
                      if (!preroll) return null;
                      return (
                        <div key={id} style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                          padding: '8px 10px',
                          borderBottom: index < selectedPrerollIds.length - 1 ? '1px solid var(--border-color)' : 'none',
                          background: 'var(--hover-bg)'
                        }}>
                          <span style={{
                            minWidth: '24px',
                            height: '24px',
                            borderRadius: '4px',
                            background: 'var(--accent-color)',
                            color: 'white',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: '11px',
                            fontWeight: 'bold'
                          }}>{index + 1}</span>
                          <span style={{
                            flex: 1,
                            color: 'var(--text-color)',
                            fontSize: '12px',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap'
                          }}>
                            {preroll.display_name || preroll.filename}
                          </span>
                          <div style={{ display: 'flex', gap: '2px' }}>
                            <button
                              type="button"
                              onClick={() => movePrerollUp(index)}
                              disabled={index === 0}
                              title="Move up"
                              style={{
                                padding: '4px',
                                border: 'none',
                                background: 'var(--button-secondary-bg)',
                                color: 'var(--button-text)',
                                borderRadius: '4px',
                                cursor: index === 0 ? 'not-allowed' : 'pointer',
                                opacity: index === 0 ? 0.3 : 1,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center'
                              }}
                            >
                              <ChevronUp size={14} />
                            </button>
                            <button
                              type="button"
                              onClick={() => movePrerollDown(index)}
                              disabled={index === selectedPrerollIds.length - 1}
                              title="Move down"
                              style={{
                                padding: '4px',
                                border: 'none',
                                background: 'var(--button-secondary-bg)',
                                color: 'var(--button-text)',
                                borderRadius: '4px',
                                cursor: index === selectedPrerollIds.length - 1 ? 'not-allowed' : 'pointer',
                                opacity: index === selectedPrerollIds.length - 1 ? 0.3 : 1,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center'
                              }}
                            >
                              <ChevronDown size={14} />
                            </button>
                            <button
                              type="button"
                              onClick={() => removePreroll(id)}
                              title="Remove"
                              style={{
                                padding: '4px',
                                border: 'none',
                                background: '#f56565',
                                color: 'white',
                                borderRadius: '4px',
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center'
                              }}
                            >
                              <X size={14} />
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              <div style={{ marginBottom: '8px' }}>
                <label style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  marginBottom: '6px',
                  color: 'var(--text-color)',
                  fontWeight: 600,
                  fontSize: '13px'
                }}>
                  <Search size={16} />
                  {selectedPrerollIds.length === 0 ? 'Select Prerolls' : 'Add More'}
                </label>
                <input
                  type="text"
                  placeholder="Search prerolls..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  style={{
                    width: '80%',
                    padding: '9px 12px',
                    border: '2px solid var(--border-color)',
                    borderRadius: '6px',
                    background: 'var(--input-bg)',
                    color: 'var(--text-color)',
                    fontSize: '13px',
                    marginBottom: '8px'
                  }}
                />
                <div style={{
                  border: '2px solid var(--border-color)',
                  borderRadius: '6px',
                  background: 'var(--card-bg)',
                  maxHeight: selectedPrerollIds.length > 0 ? '200px' : '320px',
                  overflowY: 'auto'
                }}>
                  {Object.keys(prerollsByCategory).length === 0 ? (
                    <div style={{
                      padding: '24px',
                      textAlign: 'center',
                      color: 'var(--text-secondary)',
                      fontSize: '13px'
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
                              padding: '10px 12px',
                              background: 'var(--hover-bg)',
                              borderBottom: '1px solid var(--border-color)',
                              cursor: 'pointer',
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                              fontWeight: 600,
                              fontSize: '13px',
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
                                  gap: '8px',
                                  padding: '9px 12px 9px 28px',
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
                                  style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                                />
                                <span style={{
                                  flex: 1,
                                  color: 'var(--text-color)',
                                  fontSize: '13px',
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                  whiteSpace: 'nowrap'
                                }}>
                                  {preroll.display_name || preroll.filename}
                                </span>
                                {isSelected && (
                                  <span style={{
                                    background: 'var(--accent-color)',
                                    color: 'white',
                                    padding: '2px 7px',
                                    borderRadius: '10px',
                                    fontSize: '10px',
                                    fontWeight: 'bold',
                                    minWidth: '22px',
                                    textAlign: 'center'
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

          {/* NeX-Up Trailers Configuration */}
          {blockType === 'nexup_trailers' && (
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '12px', marginBottom: '12px' }}>
              <div>
                <label style={{
                  display: 'block',
                  marginBottom: '6px',
                  color: 'var(--text-color)',
                  fontWeight: 600,
                  fontSize: '13px'
                }}>Source</label>
                <select
                  value={nexupSource}
                  onChange={(e) => setNexupSource(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '9px 12px',
                    border: '2px solid var(--border-color)',
                    borderRadius: '6px',
                    background: 'var(--input-bg)',
                    color: 'var(--text-color)',
                    fontSize: '13px',
                    cursor: 'pointer'
                  }}
                >
                  <option value="both">Movies &amp; TV</option>
                  <option value="movies">Movies Only</option>
                  <option value="tv">TV Shows Only</option>
                </select>
                <small style={{ display: 'block', marginTop: '5px', color: 'var(--text-secondary)', fontSize: '11px' }}>
                  Pull trailers from NeX-Up's downloaded coming soon trailers
                </small>
              </div>
              <div>
                <label style={{
                  display: 'block',
                  marginBottom: '6px',
                  color: 'var(--text-color)',
                  fontWeight: 600,
                  fontSize: '13px'
                }}>Count</label>
                <input
                  type="number"
                  min="1"
                  max="20"
                  value={nexupCount}
                  onChange={(e) => setNexupCount(Math.max(1, parseInt(e.target.value) || 1))}
                  style={{
                    width: '100%',
                    padding: '9px 12px',
                    border: '2px solid var(--border-color)',
                    borderRadius: '6px',
                    background: 'var(--input-bg)',
                    color: 'var(--text-color)',
                    fontSize: '13px',
                    boxSizing: 'border-box'
                  }}
                />
                <small style={{ display: 'block', marginTop: '5px', color: 'var(--text-secondary)', fontSize: '11px' }}>
                  Number of trailers to pick
                </small>
              </div>
            </div>
          )}

          {/* Coming Soon List Configuration */}
          {blockType === 'coming_soon_list' && (
            <div style={{ marginBottom: '12px' }}>
              <label style={{
                display: 'block',
                marginBottom: '6px',
                color: 'var(--text-color)',
                fontWeight: 600,
                fontSize: '13px'
              }}>Layout Style</label>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                {['grid', 'list'].map((layout) => (
                  <button
                    key={layout}
                    type="button"
                    onClick={() => setComingSoonLayout(layout)}
                    style={{
                      padding: '14px',
                      border: comingSoonLayout === layout ? '2px solid var(--accent-color)' : '2px solid var(--border-color)',
                      borderRadius: '8px',
                      background: comingSoonLayout === layout ? 'rgba(79, 172, 254, 0.1)' : 'var(--card-bg)',
                      color: 'var(--text-color)',
                      cursor: 'pointer',
                      transition: 'all 0.3s',
                      textAlign: 'center',
                      fontWeight: comingSoonLayout === layout ? 'bold' : 'normal',
                      fontSize: '14px',
                      textTransform: 'capitalize'
                    }}
                  >
                    {layout === 'grid' ? 'Grid Layout' : 'List Layout'}
                  </button>
                ))}
              </div>
              <small style={{ display: 'block', marginTop: '8px', color: 'var(--text-secondary)', fontSize: '11px' }}>
                Plays the auto-generated Coming Soon List video showing upcoming releases
              </small>
            </div>
          )}

          {/* Dynamic Preroll Configuration */}
          {blockType === 'dynamic_preroll' && (
            <div style={{ marginBottom: '12px' }}>
              {dynamicPrerollsLoading ? (
                <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-secondary)' }}>
                  Loading available prerolls...
                </div>
              ) : dynamicPrerolls.length === 0 ? (
                <div style={{
                  textAlign: 'center',
                  padding: '20px',
                  color: 'var(--text-secondary)',
                  background: 'var(--hover-bg)',
                  borderRadius: '8px',
                  border: '1px solid var(--border-color)'
                }}>
                  No dynamic prerolls generated yet. Generate them in the NeX-Up settings.
                </div>
              ) : (
                <>
                  <label style={{
                    display: 'block',
                    marginBottom: '8px',
                    color: 'var(--text-color)',
                    fontWeight: 600,
                    fontSize: '13px'
                  }}>Select Dynamic Preroll</label>
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                    gap: '8px'
                  }}>
                    {dynamicPrerolls.map((dp) => {
                      const parts = dp.template_id.split('_');
                      const theme = parts[parts.length - 1];
                      const template = parts.slice(0, -1).join('_');
                      const isSelected = dpTemplate === template && dpTheme === theme;
                      return (
                        <button
                          key={dp.filename}
                          type="button"
                          onClick={() => { setDpTemplate(template); setDpTheme(theme); }}
                          style={{
                            padding: '12px',
                            border: isSelected ? '2px solid var(--accent-color)' : '2px solid var(--border-color)',
                            borderRadius: '8px',
                            background: isSelected ? 'rgba(67, 233, 123, 0.1)' : 'var(--card-bg)',
                            color: 'var(--text-color)',
                            cursor: 'pointer',
                            transition: 'all 0.3s',
                            textAlign: 'left'
                          }}
                        >
                          <div style={{ fontWeight: 'bold', fontSize: '13px', marginBottom: '4px', textTransform: 'capitalize' }}>
                            {template.replace(/_/g, ' ')}
                          </div>
                          <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'capitalize' }}>
                            Theme: {theme}
                          </div>
                          <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                            {(dp.size_bytes / 1024 / 1024).toFixed(1)} MB
                          </div>
                        </button>
                      );
                    })}
                  </div>
                  <small style={{ display: 'block', marginTop: '8px', color: 'var(--text-secondary)', fontSize: '11px' }}>
                    Select a generated dynamic preroll to include in the sequence
                  </small>
                </>
              )}
            </div>
          )}
        </div>

        <div style={{
          padding: '14px 20px',
          borderTop: '2px solid var(--border-color)',
          display: 'flex',
          justifyContent: 'flex-end',
          gap: '10px',
          background: 'var(--hover-bg)'
        }}>
          <button type="button" style={{
            padding: '9px 20px',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            fontSize: '13px',
            fontWeight: 600,
            transition: 'all 0.3s',
            background: 'var(--button-secondary-bg)',
            color: 'var(--button-text)',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }} onClick={onCancel}>
            <X size={16} />
            Cancel
          </button>
          <button 
            type="button"
            style={{
              padding: '9px 20px',
              border: 'none',
              borderRadius: '6px',
              cursor: canSave ? 'pointer' : 'not-allowed',
              fontSize: '13px',
              fontWeight: 600,
              transition: 'all 0.3s',
              background: 'var(--button-bg)',
              color: 'white',
              opacity: canSave ? 1 : 0.5,
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
            onClick={handleSave}
            disabled={!canSave}
          >
            <Check size={16} />
            {isNew ? 'Add Block' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default BlockEditor;
