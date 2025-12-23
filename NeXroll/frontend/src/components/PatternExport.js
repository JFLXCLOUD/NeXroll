import React, { useState } from 'react';
import { Upload, Package, AlertTriangle, Loader2, Lightbulb, Sparkles } from 'lucide-react';

/**
 * PatternExport - Export sequence with multiple format options
 * Shows export mode selection and handles download
 * 
 * Props:
 * - isOpen: Boolean - whether modal is visible
 * - onClose: Function - callback to close modal
 * - scheduleId: Number - ID of schedule to export
 * - scheduleName: String - name of schedule
 */
const PatternExport = ({ isOpen, onClose, scheduleId, scheduleName }) => {
  const [isExporting, setIsExporting] = useState(false);
  const [exportProgress, setExportProgress] = useState('');
  const [error, setError] = useState(null);
  const [exportMode, setExportMode] = useState('with_community_ids');

  const handleExport = async () => {
    setIsExporting(true);
    setError(null);
    setExportProgress('Preparing export...');

    try {
      // Show different progress messages based on mode
      if (exportMode === 'full_bundle') {
        setExportProgress('Packaging video files... (this may take a minute)');
      } else {
        setExportProgress('Creating pattern file...');
      }

      const response = await fetch(`/sequences/${scheduleId}/export?export_mode=${exportMode}`, {
        method: 'POST',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Export failed');
      }

      // Handle different response types based on mode
      if (exportMode === 'full_bundle') {
        setExportProgress('Downloading bundle...');
        // Full bundle returns a ZIP file
        const blob = await response.blob();
        setExportProgress('Saving file...');
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${(scheduleName || 'sequence').replace(/[^a-z0-9]/gi, '_')}_bundle.zip`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        setExportProgress('Bundle exported successfully!');
        setTimeout(() => {
          onClose();
        }, 1500);
      } else {
        setExportProgress('Downloading pattern...');
        // Other modes return JSON
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
        
        setExportProgress('Pattern exported successfully!');
        setTimeout(() => {
          onClose();
        }, 1500);
      }
    } catch (err) {
      console.error('Export error:', err);
      setError(err.message || 'Failed to export pattern');
      setExportProgress('');
    } finally {
      setIsExporting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Add spinner animation */}
      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
      
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
        <h2 style={{ margin: 0, marginBottom: '1rem', color: 'var(--text-color)', fontSize: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Upload size={24} /> Export Sequence Pattern
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
            <strong>Choose Export Format</strong>
          </p>
          <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.85rem', color: '#9ca3af', lineHeight: '1.5' }}>
            Select how much detail to include in your export. More detail makes importing easier but increases file size.
          </p>
        </div>

        {/* Export Mode Selection */}
        <div style={{ marginBottom: '1.5rem' }}>
          <h3 style={{ margin: 0, marginBottom: '0.75rem', fontSize: '1rem', color: 'var(--text-color)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Package size={18} /> Export Mode:
          </h3>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {/* Pattern Only */}
            <label
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.75rem',
                padding: '0.75rem',
                backgroundColor: exportMode === 'pattern_only' ? 'rgba(102, 126, 234, 0.15)' : 'var(--hover-bg)',
                borderRadius: '0.5rem',
                border: `2px solid ${exportMode === 'pattern_only' ? '#667eea' : 'var(--border-color)'}`,
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
            >
              <input
                type="radio"
                value="pattern_only"
                checked={exportMode === 'pattern_only'}
                onChange={(e) => setExportMode(e.target.value)}
                style={{ marginTop: '0.25rem', cursor: 'pointer' }}
              />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '0.9rem', fontWeight: 'bold', color: 'var(--text-color)', marginBottom: '0.25rem' }}>
                  Pattern Only
                </div>
                <div style={{ fontSize: '0.8rem', color: '#9ca3af', lineHeight: '1.4' }}>
                  Structure only (blocks, categories, counts). ~5KB. Recipient must have matching prerolls.
                </div>
              </div>
            </label>

            {/* With Community IDs (Recommended) */}
            <label
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.75rem',
                padding: '0.75rem',
                backgroundColor: exportMode === 'with_community_ids' ? 'rgba(16, 185, 129, 0.15)' : 'var(--hover-bg)',
                borderRadius: '0.5rem',
                border: `2px solid ${exportMode === 'with_community_ids' ? '#10b981' : 'var(--border-color)'}`,
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
            >
              <input
                type="radio"
                value="with_community_ids"
                checked={exportMode === 'with_community_ids'}
                onChange={(e) => setExportMode(e.target.value)}
                style={{ marginTop: '0.25rem', cursor: 'pointer' }}
              />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '0.9rem', fontWeight: 'bold', color: 'var(--text-color)', marginBottom: '0.25rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  With Community IDs <span style={{ color: '#10b981', fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: '0.15rem' }}><Sparkles size={12} /> RECOMMENDED</span>
                </div>
                <div style={{ fontSize: '0.8rem', color: '#9ca3af', lineHeight: '1.4' }}>
                  Includes Community Preroll IDs. ~7KB. Enables automatic re-download on import. Best for sharing!
                </div>
              </div>
            </label>

            {/* With Preroll Metadata */}
            <label
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.75rem',
                padding: '0.75rem',
                backgroundColor: exportMode === 'with_preroll_data' ? 'rgba(102, 126, 234, 0.15)' : 'var(--hover-bg)',
                borderRadius: '0.5rem',
                border: `2px solid ${exportMode === 'with_preroll_data' ? '#667eea' : 'var(--border-color)'}`,
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
            >
              <input
                type="radio"
                value="with_preroll_data"
                checked={exportMode === 'with_preroll_data'}
                onChange={(e) => setExportMode(e.target.value)}
                style={{ marginTop: '0.25rem', cursor: 'pointer' }}
              />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '0.9rem', fontWeight: 'bold', color: 'var(--text-color)', marginBottom: '0.25rem' }}>
                  With Preroll Metadata
                </div>
                <div style={{ fontSize: '0.8rem', color: '#9ca3af', lineHeight: '1.4' }}>
                  Full metadata (names, tags, duration, descriptions). ~50KB. Helps recipients find equivalents.
                </div>
              </div>
            </label>

            {/* Full Bundle */}
            <label
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.75rem',
                padding: '0.75rem',
                backgroundColor: exportMode === 'full_bundle' ? 'rgba(245, 158, 11, 0.15)' : 'var(--hover-bg)',
                borderRadius: '0.5rem',
                border: `2px solid ${exportMode === 'full_bundle' ? '#f59e0b' : 'var(--border-color)'}`,
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
            >
              <input
                type="radio"
                value="full_bundle"
                checked={exportMode === 'full_bundle'}
                onChange={(e) => setExportMode(e.target.value)}
                style={{ marginTop: '0.25rem', cursor: 'pointer' }}
              />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '0.9rem', fontWeight: 'bold', color: 'var(--text-color)', marginBottom: '0.25rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  Full Bundle (ZIP) <span style={{ color: '#f59e0b', fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: '0.15rem' }}><AlertTriangle size={12} /> LARGE FILE</span>
                </div>
                <div style={{ fontSize: '0.8rem', color: '#9ca3af', lineHeight: '1.4' }}>
                  Pattern + all video files. 100MB-5GB. Ready to import immediately. Perfect for archiving.
                </div>
              </div>
            </label>
          </div>
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
            <p style={{ margin: 0, fontSize: '0.9rem', color: '#ef4444', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <AlertTriangle size={16} /> {error}
            </p>
          </div>
        )}

        {/* Progress Message */}
        {isExporting && exportProgress && (
          <div
            style={{
              backgroundColor: 'rgba(102, 126, 234, 0.1)',
              borderRadius: '0.5rem',
              padding: '1rem',
              marginBottom: '1.5rem',
              border: '2px solid rgba(102, 126, 234, 0.4)',
              display: 'flex',
              alignItems: 'center',
              gap: '1rem',
            }}
          >
            <div
              style={{
                width: '24px',
                height: '24px',
                border: '3px solid rgba(102, 126, 234, 0.3)',
                borderTop: '3px solid #667eea',
                borderRadius: '50%',
                animation: 'spin 1s linear infinite',
              }}
            />
            <p style={{ margin: 0, fontSize: '0.95rem', color: '#667eea', fontWeight: 'bold' }}>
              {exportProgress}
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
                        {isExporting ? <><Loader2 size={16} className="spin" /> Exporting...</> : <><Upload size={16} /> Export Pattern</>}
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
          <p style={{ margin: 0, display: 'flex', alignItems: 'flex-start', gap: '0.35rem' }}>
            <Lightbulb size={14} style={{ marginTop: '0.1rem', flexShrink: 0 }} /> <span><strong>Tip:</strong> Use "With Community IDs" mode for the best sharing experience. Recipients can 
            automatically download missing prerolls from the community library when importing.</span>
          </p>
        </div>
      </div>
    </div>
    </>
  );
};

export default PatternExport;
