import React, { useState } from 'react';

/**
 * PatternImport - Import sequence from .nexseq JSON pattern file
 * Shows preview, match status, and validation warnings before creating schedule
 * 
 * Props:
 * - isOpen: Boolean - whether modal is visible
 * - onClose: Function - callback to close modal
 * - onImportSuccess: Function - callback with imported sequence data
 */
const PatternImport = ({ isOpen, onClose, onImportSuccess }) => {
  const [selectedFile, setSelectedFile] = useState(null);
  const [isImporting, setIsImporting] = useState(false);
  const [previewData, setPreviewData] = useState(null);
  const [error, setError] = useState(null);

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (file) {
      if (!file.name.endsWith('.nexseq') && !file.name.endsWith('.json')) {
        setError('Please select a .nexseq or .json file');
        return;
      }
      setSelectedFile(file);
      setError(null);
      setPreviewData(null);
    }
  };

  const handlePreview = async () => {
    if (!selectedFile) return;

    setIsImporting(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const response = await fetch('/api/sequences/import', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Import failed');
      }

      const data = await response.json();
      setPreviewData(data);
    } catch (err) {
      console.error('Import preview error:', err);
      setError(err.message || 'Failed to preview pattern');
    } finally {
      setIsImporting(false);
    }
  };

  const handleConfirmImport = () => {
    if (!previewData) return;

    // Pass the imported blocks back to parent component (App.js)
    // Parent will create a new schedule with this sequence
    onImportSuccess({
      name: previewData.pattern_name,
      blocks: previewData.blocks,
      sequenceJson: previewData.sequence_json,
      matchResults: previewData.match_results
    });
    
    // Reset state
    setSelectedFile(null);
    setPreviewData(null);
    setError(null);
    onClose();
  };

  const handleReset = () => {
    setSelectedFile(null);
    setPreviewData(null);
    setError(null);
  };

  if (!isOpen) return null;

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
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          backgroundColor: 'var(--card-bg)',
          borderRadius: '0.5rem',
          padding: '2rem',
          maxWidth: '700px',
          width: '100%',
          maxHeight: '90vh',
          overflowY: 'auto',
          border: '1px solid var(--border-color)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <h2 style={{ margin: 0, marginBottom: '1rem', color: 'var(--text-color)', fontSize: '1.5rem' }}>
          📥 Import Sequence Pattern
        </h2>

        {/* File Upload Section */}
        {!previewData && (
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
                <strong>Import a .nexseq pattern file</strong>
              </p>
              <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.85rem', color: '#9ca3af', lineHeight: '1.5' }}>
                Select a pattern file exported from NeXroll. The system will automatically match prerolls and categories
                to your library using Community Preroll IDs and fuzzy name matching.
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
                Select Pattern File:
              </label>
              <input
                type="file"
                accept=".nexseq,.json"
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
                <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.85rem', color: '#10b981' }}>
                  ✅ Selected: {selectedFile.name} ({(selectedFile.size / 1024).toFixed(2)} KB)
                </p>
              )}
            </div>
          </>
        )}

        {/* Preview Section */}
        {previewData && (
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
              <h3 style={{ margin: 0, marginBottom: '1rem', fontSize: '1.1rem', color: 'var(--text-color)' }}>
                📋 Pattern Preview
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
                  gridTemplateColumns: 'repeat(3, 1fr)',
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
                  <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '0.25rem' }}>Matched</div>
                </div>
                <div
                  style={{
                    backgroundColor: 'rgba(245, 158, 11, 0.1)',
                    borderRadius: '0.5rem',
                    padding: '0.75rem',
                    textAlign: 'center',
                    border: '1px solid rgba(245, 158, 11, 0.3)',
                  }}
                >
                  <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#f59e0b' }}>
                    {previewData.match_results.unmatched}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '0.25rem' }}>Unmatched</div>
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
                  <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '0.25rem' }}>Total Blocks</div>
                </div>
              </div>
            </div>

            {/* Missing Items Warning */}
            {(previewData.match_results.missing_categories.length > 0 ||
              previewData.match_results.missing_prerolls.length > 0) && (
              <div
                style={{
                  backgroundColor: 'rgba(245, 158, 11, 0.1)',
                  borderRadius: '0.5rem',
                  padding: '1rem',
                  marginBottom: '1.5rem',
                  border: '1px solid rgba(245, 158, 11, 0.3)',
                }}
              >
                <h4 style={{ margin: 0, marginBottom: '0.75rem', fontSize: '0.95rem', color: '#f59e0b' }}>
                  ⚠️ Missing Items
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

                {previewData.match_results.missing_prerolls.length > 0 && (
                  <div>
                    <div style={{ fontSize: '0.85rem', color: 'var(--text-color)', marginBottom: '0.5rem' }}>
                      <strong>Prerolls not found:</strong>
                    </div>
                    <ul style={{ margin: 0, paddingLeft: '1.5rem', fontSize: '0.8rem', color: '#9ca3af' }}>
                      {previewData.match_results.missing_prerolls.slice(0, 5).map((preroll, idx) => (
                        <li key={idx}>
                          {preroll.name}
                          {preroll.community_id && (
                            <span style={{ marginLeft: '0.5rem', color: '#667eea' }}>
                              (Community ID: {preroll.community_id})
                            </span>
                          )}
                        </li>
                      ))}
                      {previewData.match_results.missing_prerolls.length > 5 && (
                        <li style={{ color: '#f59e0b' }}>
                          +{previewData.match_results.missing_prerolls.length - 5} more...
                        </li>
                      )}
                    </ul>
                  </div>
                )}

                <p style={{ margin: '0.75rem 0 0 0', fontSize: '0.8rem', color: '#9ca3af' }}>
                  💡 Consider downloading missing prerolls from Community Prerolls before importing.
                </p>
              </div>
            )}
          </>
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
            <p style={{ margin: 0, fontSize: '0.9rem', color: '#ef4444' }}>
              ⚠️ {error}
            </p>
          </div>
        )}

        {/* Action Buttons */}
        <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
          {!previewData ? (
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
                disabled={!selectedFile || isImporting}
                style={{
                  padding: '0.75rem 1.5rem',
                  backgroundColor: !selectedFile || isImporting ? '#9ca3af' : '#667eea',
                  color: 'white',
                  border: 'none',
                  borderRadius: '0.5rem',
                  cursor: !selectedFile || isImporting ? 'not-allowed' : 'pointer',
                  fontSize: '1rem',
                  fontWeight: 'bold',
                }}
              >
                {isImporting ? '⏳ Loading...' : '👁️ Preview Import'}
              </button>
            </>
          ) : (
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
                }}
              >
                ← Back
              </button>
              <button
                onClick={handleConfirmImport}
                disabled={previewData.match_results.matched === 0}
                style={{
                  padding: '0.75rem 1.5rem',
                  backgroundColor: previewData.match_results.matched === 0 ? '#9ca3af' : '#10b981',
                  color: 'white',
                  border: 'none',
                  borderRadius: '0.5rem',
                  cursor: previewData.match_results.matched === 0 ? 'not-allowed' : 'pointer',
                  fontSize: '1rem',
                  fontWeight: 'bold',
                }}
              >
                ✅ Import Pattern
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default PatternImport;
