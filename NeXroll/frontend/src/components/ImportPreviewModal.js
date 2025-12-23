import React, { useState, useEffect } from 'react';
import '../App.css';

const ImportPreviewModal = ({ 
  importData, 
  onConfirm, 
  onCancel, 
  apiUrl,
  showAlert 
}) => {
  const [downloading, setDownloading] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState({});
  const [prerollMappings, setPrerollMappings] = useState({});
  const [availablePrerolls, setAvailablePrerolls] = useState([]);
  const [creatingCategories, setCreatingCategories] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');

  const matchResults = importData.match_results || {};
  const missingPrerolls = matchResults.missing_prerolls || [];
  const missingCategories = matchResults.missing_categories || [];
  const downloadablePrerolls = missingPrerolls.filter(p => p.downloadable);
  const unavailablePrerolls = missingPrerolls.filter(p => !p.downloadable);

  // Debug logging
  console.log('[ImportPreview] Missing prerolls:', missingPrerolls);
  console.log('[ImportPreview] Downloadable prerolls:', downloadablePrerolls);

  useEffect(() => {
    // Fetch available prerolls for manual mapping
    fetch(apiUrl('prerolls'))
      .then(res => res.json())
      .then(data => setAvailablePrerolls(data))
      .catch(err => console.error('Failed to load prerolls:', err));
  }, [apiUrl]);

  const downloadPreroll = async (preroll) => {
    if (!preroll.community_id) return;

    console.log('[ImportPreview] Downloading preroll:', { 
      name: preroll.name, 
      community_id: preroll.community_id,
      category: preroll.category
    });

    setDownloadProgress(prev => ({ ...prev, [preroll.community_id]: 'downloading' }));

    try {
      // Look up category_id if category name(s) are provided
      let category_id = null;
      const categoryNames = preroll.category_names || (preroll.category ? [preroll.category] : []);
      
      if (categoryNames && categoryNames.length > 0) {
        try {
          const categoriesRes = await fetch(apiUrl('categories'));
          const categories = await categoriesRes.json();
          // Use the first matching category
          for (const catName of categoryNames) {
            const matchedCategory = categories.find(c => c.name === catName);
            if (matchedCategory) {
              category_id = matchedCategory.id;
              console.log(`[ImportPreview] Matched category '${catName}' -> ID ${category_id}`);
              break;
            }
          }
          if (!category_id) {
            console.warn(`[ImportPreview] No matching category found for: ${categoryNames.join(', ')}`);
          }
        } catch (err) {
          console.warn('Failed to look up category:', err);
        }
      }

      const response = await fetch(apiUrl('community-prerolls/download'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          preroll_id: preroll.community_id,
          title: preroll.name,
          category_id: category_id,
          add_to_category: true
        })
      });

      if (response.ok) {
        const result = await response.json();
        setDownloadProgress(prev => ({ ...prev, [preroll.community_id]: 'success' }));
        showAlert(`✅ Downloaded: ${preroll.name}`, 'success');
        
        // Remove from missing list by marking as downloaded
        const updatedMissing = missingPrerolls.filter(p => p.community_id !== preroll.community_id);
        importData.match_results.missing_prerolls = updatedMissing;
        
        // Refresh available prerolls
        const prerollsData = await fetch(apiUrl('prerolls')).then(r => r.json());
        setAvailablePrerolls(prerollsData);
      } else {
        const error = await response.json();
        setDownloadProgress(prev => ({ ...prev, [preroll.community_id]: 'error' }));
        showAlert(`❌ Download failed: ${error.detail || 'Unknown error'}`, 'error');
      }
    } catch (err) {
      setDownloadProgress(prev => ({ ...prev, [preroll.community_id]: 'error' }));
      showAlert(`❌ Download error: ${err.message}`, 'error');
    }
  };

  const downloadAllPrerolls = async () => {
    if (downloadablePrerolls.length === 0) return;

    setDownloading(true);
    let successCount = 0;
    let errorCount = 0;

    for (const preroll of downloadablePrerolls) {
      try {
        await downloadPreroll(preroll);
        successCount++;
      } catch (err) {
        errorCount++;
      }
    }

    setDownloading(false);
    showAlert(
      `✅ Downloaded ${successCount} prerolls${errorCount > 0 ? `, ${errorCount} failed` : ''}`,
      errorCount > 0 ? 'warning' : 'success'
    );
  };

  const createCategory = async (categoryName) => {
    try {
      const response = await fetch(apiUrl('categories'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: categoryName })
      });

      if (response.ok) {
        showAlert(`✅ Created category: ${categoryName}`, 'success');
        // Remove from missing list
        const updatedMissing = missingCategories.filter(c => c !== categoryName);
        importData.match_results.missing_categories = updatedMissing;
        return true;
      } else {
        const error = await response.json();
        showAlert(`❌ Failed to create category: ${error.detail}`, 'error');
        return false;
      }
    } catch (err) {
      showAlert(`❌ Error creating category: ${err.message}`, 'error');
      return false;
    }
  };

  const createAllCategories = async () => {
    if (missingCategories.length === 0) return;

    setCreatingCategories(true);
    let successCount = 0;

    for (const category of missingCategories) {
      const success = await createCategory(category);
      if (success) successCount++;
    }

    setCreatingCategories(false);
    showAlert(`✅ Created ${successCount} categories`, 'success');
  };

  const handleMapPreroll = (missingPrerollName, selectedPrerollId) => {
    setPrerollMappings(prev => ({
      ...prev,
      [missingPrerollName]: selectedPrerollId
    }));
  };

  const handleConfirm = () => {
    // Apply mappings to blocks before confirming
    if (Object.keys(prerollMappings).length > 0) {
      importData.blocks.forEach(block => {
        if (block.type === 'fixed' && block._missing_prerolls) {
          block._missing_prerolls.forEach(missingName => {
            if (prerollMappings[missingName]) {
              block.preroll_ids = [parseInt(prerollMappings[missingName])];
              delete block._unmatched;
              delete block._missing_prerolls;
            }
          });
        }
      });
    }

    onConfirm(importData);
  };

  // Import is allowed if:
  // 1. No missing categories (categories must be created first)
  // 2. No unavailable prerolls, OR all unavailable prerolls have been manually mapped
  const unmappedUnavailablePrerolls = unavailablePrerolls.filter(
    p => !prerollMappings[p.name]
  );
  const canImport = missingCategories.length === 0 && unmappedUnavailablePrerolls.length === 0;
  
  const totalBlocks = matchResults.total_blocks || 0;
  const matchedBlocks = matchResults.matched || 0;

  return (
    <div className="nx-modal-overlay" onClick={(e) => e.target.classList.contains('nx-modal-overlay') && onCancel()}>
      <div className="nx-modal" style={{ maxWidth: '800px', maxHeight: '90vh', overflow: 'auto' }}>
        <div className="nx-modal-header">
          <h3 className="nx-modal-title">📥 Import Preview: {importData.pattern_name}</h3>
          <button className="nx-modal-close" onClick={onCancel}>×</button>
        </div>

        <div className="nx-modal-body">
          {/* Tabs */}
          <div className="import-tabs" style={{ 
            display: 'flex', 
            gap: '10px', 
            marginBottom: '20px', 
            borderBottom: '2px solid var(--border-color)' 
          }}>
            <button
              onClick={() => setActiveTab('overview')}
              style={{
                padding: '10px 20px',
                background: activeTab === 'overview' ? 'var(--primary-color)' : 'transparent',
                color: activeTab === 'overview' ? 'white' : 'var(--text-color)',
                border: 'none',
                borderBottom: activeTab === 'overview' ? '3px solid var(--primary-color)' : 'none',
                cursor: 'pointer'
              }}
            >
              Overview
            </button>
            {downloadablePrerolls.length > 0 && (
              <button
                onClick={() => setActiveTab('downloads')}
                style={{
                  padding: '10px 20px',
                  background: activeTab === 'downloads' ? 'var(--primary-color)' : 'transparent',
                  color: activeTab === 'downloads' ? 'white' : 'var(--text-color)',
                  border: 'none',
                  borderBottom: activeTab === 'downloads' ? '3px solid var(--primary-color)' : 'none',
                  cursor: 'pointer'
                }}
              >
                Downloads ({downloadablePrerolls.length})
              </button>
            )}
            {unavailablePrerolls.length > 0 && (
              <button
                onClick={() => setActiveTab('mapping')}
                style={{
                  padding: '10px 20px',
                  background: activeTab === 'mapping' ? 'var(--primary-color)' : 'transparent',
                  color: activeTab === 'mapping' ? 'white' : 'var(--text-color)',
                  border: 'none',
                  borderBottom: activeTab === 'mapping' ? '3px solid var(--primary-color)' : 'none',
                  cursor: 'pointer'
                }}
              >
                Mapping ({unavailablePrerolls.length})
              </button>
            )}
            {missingCategories.length > 0 && (
              <button
                onClick={() => setActiveTab('categories')}
                style={{
                  padding: '10px 20px',
                  background: activeTab === 'categories' ? 'var(--primary-color)' : 'transparent',
                  color: activeTab === 'categories' ? 'white' : 'var(--text-color)',
                  border: 'none',
                  borderBottom: activeTab === 'categories' ? '3px solid var(--primary-color)' : 'none',
                  cursor: 'pointer'
                }}
              >
                Categories ({missingCategories.length})
              </button>
            )}
          </div>

          {/* Overview Tab */}
          {activeTab === 'overview' && (
            <div className="overview-tab">
              <div className="import-summary">
                <h3>📊 Import Summary</h3>
                <div style={{ 
                  display: 'grid', 
                  gridTemplateColumns: '1fr 1fr', 
                  gap: '15px', 
                  marginTop: '15px' 
                }}>
                  <div className="stat-card" style={{ 
                    padding: '15px', 
                    background: 'var(--card-background)', 
                    borderRadius: '8px',
                    border: '1px solid var(--border-color)'
                  }}>
                    <div style={{ fontSize: '24px', fontWeight: 'bold', color: 'var(--primary-color)' }}>
                      {matchedBlocks}/{totalBlocks}
                    </div>
                    <div style={{ color: 'var(--text-secondary)', marginTop: '5px' }}>Blocks Matched</div>
                  </div>

                  <div className="stat-card" style={{ 
                    padding: '15px', 
                    background: 'var(--card-background)', 
                    borderRadius: '8px',
                    border: '1px solid var(--border-color)'
                  }}>
                    <div style={{ fontSize: '24px', fontWeight: 'bold', color: downloadablePrerolls.length > 0 ? '#f59e0b' : '#10b981' }}>
                      {missingPrerolls.length}
                    </div>
                    <div style={{ color: 'var(--text-secondary)', marginTop: '5px' }}>Missing Prerolls</div>
                  </div>

                  <div className="stat-card" style={{ 
                    padding: '15px', 
                    background: 'var(--card-background)', 
                    borderRadius: '8px',
                    border: '1px solid var(--border-color)'
                  }}>
                    <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#10b981' }}>
                      {downloadablePrerolls.length}
                    </div>
                    <div style={{ color: 'var(--text-secondary)', marginTop: '5px' }}>Can Download</div>
                  </div>

                  <div className="stat-card" style={{ 
                    padding: '15px', 
                    background: 'var(--card-background)', 
                    borderRadius: '8px',
                    border: '1px solid var(--border-color)'
                  }}>
                    <div style={{ fontSize: '24px', fontWeight: 'bold', color: missingCategories.length > 0 ? '#f59e0b' : '#10b981' }}>
                      {missingCategories.length}
                    </div>
                    <div style={{ color: 'var(--text-secondary)', marginTop: '5px' }}>Missing Categories</div>
                  </div>
                </div>

                {importData.pattern_description && (
                  <div style={{ marginTop: '20px', padding: '15px', background: 'var(--card-background)', borderRadius: '8px' }}>
                    <strong>Description:</strong>
                    <p style={{ marginTop: '10px', color: 'var(--text-secondary)' }}>{importData.pattern_description}</p>
                  </div>
                )}

                {matchedBlocks === totalBlocks && missingPrerolls.length === 0 && missingCategories.length === 0 && (
                  <div style={{ 
                    marginTop: '20px', 
                    padding: '15px', 
                    background: '#10b98120', 
                    borderRadius: '8px',
                    border: '1px solid #10b981',
                    color: '#10b981'
                  }}>
                    ✅ All blocks matched successfully! Ready to import.
                  </div>
                )}

                {(downloadablePrerolls.length > 0 || missingCategories.length > 0) && (
                  <div style={{ 
                    marginTop: '20px', 
                    padding: '15px', 
                    background: '#f59e0b20', 
                    borderRadius: '8px',
                    border: '1px solid #f59e0b',
                    color: '#f59e0b'
                  }}>
                    ⚠️ Some items need attention before importing. Check the tabs above.
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Downloads Tab */}
          {activeTab === 'downloads' && (
            <div className="downloads-tab">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <h3>📥 Available for Download</h3>
                <button
                  onClick={downloadAllPrerolls}
                  disabled={downloading || downloadablePrerolls.length === 0}
                  className="primary-button"
                  style={{ padding: '8px 16px' }}
                >
                  {downloading ? '⏳ Downloading...' : `⬇️ Download All (${downloadablePrerolls.length})`}
                </button>
              </div>

              <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
                {downloadablePrerolls.map((preroll, index) => {
                  const progress = downloadProgress[preroll.community_id];
                  return (
                    <div
                      key={index}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '15px',
                        marginBottom: '10px',
                        background: 'var(--card-background)',
                        borderRadius: '8px',
                        border: '1px solid var(--border-color)'
                      }}
                    >
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 'bold' }}>{preroll.name}</div>
                        <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '5px' }}>
                          Community ID: {preroll.community_id}
                        </div>
                        {preroll.category && (
                          <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                            Category: {preroll.category}
                          </div>
                        )}
                      </div>

                      <div>
                        {progress === 'success' ? (
                          <span style={{ color: '#10b981', fontWeight: 'bold' }}>✓ Downloaded</span>
                        ) : progress === 'downloading' ? (
                          <span style={{ color: '#f59e0b' }}>⏳ Downloading...</span>
                        ) : progress === 'error' ? (
                          <span style={{ color: '#ef4444' }}>✗ Failed</span>
                        ) : (
                          <button
                            onClick={() => downloadPreroll(preroll)}
                            className="primary-button"
                            style={{ padding: '6px 12px', fontSize: '14px' }}
                          >
                            ⬇️ Download
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Mapping Tab */}
          {activeTab === 'mapping' && (
            <div className="mapping-tab">
              <h3>🔗 Manual Preroll Mapping</h3>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '20px' }}>
                Map unavailable prerolls to existing ones in your library:
              </p>

              <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
                {unavailablePrerolls.map((preroll, index) => (
                  <div
                    key={index}
                    style={{
                      padding: '15px',
                      marginBottom: '15px',
                      background: 'var(--card-background)',
                      borderRadius: '8px',
                      border: '1px solid var(--border-color)'
                    }}
                  >
                    <div style={{ fontWeight: 'bold', marginBottom: '10px' }}>
                      Missing: {preroll.name}
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '10px' }}>
                      Reason: {preroll.reason}
                    </div>

                    <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                      <span style={{ fontSize: '14px' }}>Map to:</span>
                      <select
                        value={prerollMappings[preroll.name] || ''}
                        onChange={(e) => handleMapPreroll(preroll.name, e.target.value)}
                        style={{
                          flex: 1,
                          padding: '8px',
                          background: 'var(--input-background)',
                          color: 'var(--text-color)',
                          border: '1px solid var(--border-color)',
                          borderRadius: '4px'
                        }}
                      >
                        <option value="">-- Select a preroll --</option>
                        {availablePrerolls.map(p => (
                          <option key={p.id} value={p.id}>
                            {p.display_name || p.filename}
                          </option>
                        ))}
                      </select>
                      {prerollMappings[preroll.name] && (
                        <span style={{ color: '#10b981' }}>✓</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {unavailablePrerolls.length === 0 && (
                <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>
                  No prerolls need mapping
                </div>
              )}
            </div>
          )}

          {/* Categories Tab */}
          {activeTab === 'categories' && (
            <div className="categories-tab">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <h3>📁 Missing Categories</h3>
                <button
                  onClick={createAllCategories}
                  disabled={creatingCategories || missingCategories.length === 0}
                  className="primary-button"
                  style={{ padding: '8px 16px' }}
                >
                  {creatingCategories ? '⏳ Creating...' : `➕ Create All (${missingCategories.length})`}
                </button>
              </div>

              <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
                {missingCategories.map((category, index) => (
                  <div
                    key={index}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '15px',
                      marginBottom: '10px',
                      background: 'var(--card-background)',
                      borderRadius: '8px',
                      border: '1px solid var(--border-color)'
                    }}
                  >
                    <div style={{ fontWeight: 'bold' }}>{category}</div>
                    <button
                      onClick={() => createCategory(category)}
                      disabled={creatingCategories}
                      className="primary-button"
                      style={{ padding: '6px 12px', fontSize: '14px' }}
                    >
                      ➕ Create
                    </button>
                  </div>
                ))}
              </div>

              {missingCategories.length === 0 && (
                <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>
                  No missing categories
                </div>
              )}
            </div>
          )}
        </div>

        <div className="modal-footer" style={{ display: 'flex', justifyContent: 'space-between', gap: '10px' }}>
          <button onClick={onCancel} className="secondary-button" style={{ flex: 1 }}>
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            className="primary-button"
            style={{ flex: 1 }}
            disabled={!canImport}
            title={
              !canImport 
                ? (missingCategories.length > 0 
                    ? 'Please create missing categories first' 
                    : 'Please map or download unavailable prerolls first')
                : downloadablePrerolls.length > 0
                  ? 'Import sequence (some prerolls can be downloaded from the modal tabs)'
                  : 'Import sequence'
            }
          >
            {downloadablePrerolls.length > 0 && canImport
              ? '⚠️ Import (Prerolls Downloadable)'
              : canImport 
                ? '✓ Import Sequence' 
                : missingCategories.length > 0
                  ? '❌ Create Categories First'
                  : '❌ Map Missing Prerolls'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ImportPreviewModal;
