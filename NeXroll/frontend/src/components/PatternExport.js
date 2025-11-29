import React, { useState } from 'react';

/**
 * PatternExport - Export sequence as lightweight .nexseq JSON pattern
 * Shows export options and handles download
 * 
 * Props:
 * - isOpen: Boolean - whether modal is visible
 * - onClose: Function - callback to close modal
 * - scheduleId: Number - ID of schedule to export
 * - scheduleName: String - name of schedule
 */
const PatternExport = ({ isOpen, onClose, scheduleId, scheduleName }) => {
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState(null);

  const handleExport = async () => {
    setIsExporting(true);
    setError(null);

    try {
      const response = await fetch(`/sequences/${scheduleId}/export`, {
        method: 'POST',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Export failed');
      }

      // Get the JSON data
      const patternData = await response.json();
      
      // Create a Blob from the JSON and trigger download
      const blob = new Blob([JSON.stringify(patternData, null, 2)], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${(scheduleName || 'sequence').replace(/[^a-z0-9]/gi, '_')}.nexseq`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);

      // Show success message
      alert('✅ Sequence pattern exported successfully!');
      onClose();
    } catch (err) {
      console.error('Export error:', err);
      setError(err.message || 'Failed to export pattern');
    } finally {
      setIsExporting(false);
    }
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
          maxWidth: '500px',
          width: '90%',
          border: '1px solid var(--border-color)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <h2 style={{ margin: 0, marginBottom: '1rem', color: 'var(--text-color)', fontSize: '1.5rem' }}>
          📤 Export Sequence Pattern
        </h2>

        {/* Description */}
        <div
          style={{
            backgroundColor: 'rgba(102, 126, 234, 0.1)',
            borderRadius: '0.5rem',
            padding: '1rem',
            marginBottom: '1.5rem',
            border: '1px solid rgba(102, 126, 234, 0.3)',
          }}
        >
          <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--text-color)', lineHeight: '1.6' }}>
            <strong>What is a pattern file?</strong>
          </p>
          <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.85rem', color: '#9ca3af', lineHeight: '1.5' }}>
            A <strong>.nexseq</strong> pattern file contains only the sequence structure (block types, categories, counts).
            It does NOT include videos. Perfect for sharing sequence designs with other NeXroll users.
          </p>
        </div>

        {/* Features */}
        <div style={{ marginBottom: '1.5rem' }}>
          <h3 style={{ margin: 0, marginBottom: '0.75rem', fontSize: '1rem', color: 'var(--text-color)' }}>
            ✨ Pattern Export Features:
          </h3>
          <ul style={{ margin: 0, paddingLeft: '1.5rem', fontSize: '0.85rem', color: '#9ca3af', lineHeight: '1.8' }}>
            <li>Lightweight JSON format (&lt;10 KB)</li>
            <li>Maps prerolls to Community Preroll IDs for cross-instance compatibility</li>
            <li>Categories referenced by name (auto-matched on import)</li>
            <li>Preserves block order and structure</li>
            <li>Easily shareable via email, Discord, or GitHub</li>
          </ul>
        </div>

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
          <button
            onClick={onClose}
            disabled={isExporting}
            style={{
              padding: '0.75rem 1.5rem',
              backgroundColor: 'transparent',
              color: 'var(--text-color)',
              border: '2px solid var(--border-color)',
              borderRadius: '0.5rem',
              cursor: isExporting ? 'not-allowed' : 'pointer',
              fontSize: '1rem',
              opacity: isExporting ? 0.5 : 1,
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleExport}
            disabled={isExporting}
            style={{
              padding: '0.75rem 1.5rem',
              backgroundColor: isExporting ? '#9ca3af' : '#667eea',
              color: 'white',
              border: 'none',
              borderRadius: '0.5rem',
              cursor: isExporting ? 'not-allowed' : 'pointer',
              fontSize: '1rem',
              fontWeight: 'bold',
            }}
          >
            {isExporting ? '⏳ Exporting...' : '📤 Export Pattern'}
          </button>
        </div>

        {/* Help Text */}
        <div
          style={{
            marginTop: '1.5rem',
            paddingTop: '1.5rem',
            borderTop: '1px solid var(--border-color)',
            fontSize: '0.8rem',
            color: '#9ca3af',
          }}
        >
          <p style={{ margin: 0 }}>
            💡 <strong>Tip:</strong> To include videos with your sequence, use "Export with Videos" instead to create a
            complete .nexpack file.
          </p>
        </div>
      </div>
    </div>
  );
};

export default PatternExport;
