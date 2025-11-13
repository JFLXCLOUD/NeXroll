import React, { useState } from 'react';

/**
 * WidgetSettingsModal - Allows users to customize what content appears in each tile
 */
const WidgetSettingsModal = ({ 
  tile = null, 
  settings = {}, 
  onSave = () => {}, 
  onClose = () => {} 
}) => {
  const [localSettings, setLocalSettings] = useState(settings);

  if (!tile) return null;

  const contentOptions = {
    plex: [
      { key: 'status', label: 'Server Status', default: true },
      { key: 'serverInfo', label: 'Server Info', default: true },
      { key: 'activeStreams', label: 'Active Streams', default: false },
      { key: 'libraryStats', label: 'Library Stats', default: false }
    ],
    prerolls: [
      { key: 'totalCount', label: 'Total Count', default: true },
      { key: 'recentUploads', label: 'Recent Uploads', default: true },
      { key: 'mostUsed', label: 'Most Used', default: false },
      { key: 'storageUsage', label: 'Storage Usage', default: false }
    ],
    schedules: [
      { key: 'activeCount', label: 'Active Count', default: true },
      { key: 'list', label: 'Schedule List', default: true },
      { key: 'nextExecution', label: 'Next Execution', default: false },
      { key: 'history', label: 'Recent History', default: false }
    ],
    categories: [
      { key: 'totalCount', label: 'Total Count', default: true },
      { key: 'list', label: 'Category List', default: true },
      { key: 'prerollCount', label: 'Preroll Count', default: false },
      { key: 'lastModified', label: 'Last Modified', default: false }
    ],
    default: [
      { key: 'title', label: 'Title', default: true },
      { key: 'content', label: 'Content', default: true }
    ]
  };

  const tileOptions = contentOptions[tile.id] || contentOptions.default;

  const handleToggle = (key) => {
    setLocalSettings(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  const handleSave = () => {
    onSave(tile.id, localSettings);
    onClose();
  };

  return (
    <div className="widget-settings-overlay">
      <div className="widget-settings-modal">
        <div className="modal-header">
          <h2>Configure {tile.title}</h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="modal-content">
          <p className="settings-description">
            Choose which information to display in this tile:
          </p>

          <div className="settings-options">
            {tileOptions.map(option => (
              <label key={option.key} className="settings-option">
                <input
                  type="checkbox"
                  checked={localSettings[option.key] !== false}
                  onChange={() => handleToggle(option.key)}
                  className="settings-checkbox"
                />
                <span className="settings-label">{option.label}</span>
              </label>
            ))}
          </div>

          <div className="settings-preview">
            <h4>Preview:</h4>
            <div className="preview-content">
              {Object.entries(localSettings).filter(([_, enabled]) => enabled).length > 0 ? (
                <ul>
                  {Object.entries(localSettings)
                    .filter(([_, enabled]) => enabled)
                    .map(([key]) => (
                      <li key={key}>{tileOptions.find(o => o.key === key)?.label}</li>
                    ))}
                </ul>
              ) : (
                <p className="preview-empty">No content selected</p>
              )}
            </div>
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn-cancel" onClick={onClose}>Cancel</button>
          <button className="btn-save" onClick={handleSave}>Save Changes</button>
        </div>
      </div>
    </div>
  );
};

export default WidgetSettingsModal;
