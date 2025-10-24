import React, { useState, useEffect } from 'react';
import GridLayout from 'react-grid-layout';
import '../../node_modules/react-grid-layout/css/styles.css';
import '../../node_modules/react-resizable/css/styles.css';

/**
 * ResizableDashboard - Manages resizable and reorderable dashboard tiles
 * Features:
 * - Drag to reorder tiles
 * - Resize tiles by dragging corners
 * - Edit mode toggle for better UX
 * - Save layout to localStorage
 * - Customize what content each tile displays
 */
const ResizableDashboard = ({ 
  tiles = [], 
  onLayoutChange = () => {},
  isEditMode = false,
  onEditModeChange = () => {}
}) => {
  const [layout, setLayout] = useState([]);
  const [widgetSettings, setWidgetSettings] = useState(() => {
    try {
      const saved = localStorage.getItem('dashboardWidgetSettings');
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  });

  // Initialize layout from tiles
  useEffect(() => {
    if (tiles.length > 0) {
      const savedLayout = localStorage.getItem('dashboardLayout');
      if (savedLayout) {
        try {
          setLayout(JSON.parse(savedLayout));
          return;
        } catch {}
      }

      // Generate default layout (4 columns, 1 row height)
      const defaultLayout = tiles.map((tile, idx) => ({
        x: (idx % 4) * 3,
        y: Math.floor(idx / 4) * 3,
        w: 3,
        h: 3,
        i: tile.id,
        static: false
      }));
      setLayout(defaultLayout);
    }
  }, [tiles]);

  const handleLayoutChange = (newLayout) => {
    setLayout(newLayout);
    localStorage.setItem('dashboardLayout', JSON.stringify(newLayout));
    onLayoutChange(newLayout);
  };

  const toggleWidgetContent = (tileId, contentKey) => {
    const newSettings = {
      ...widgetSettings,
      [tileId]: {
        ...(widgetSettings[tileId] || {}),
        [contentKey]: !(widgetSettings[tileId]?.[contentKey] ?? true)
      }
    };
    setWidgetSettings(newSettings);
    localStorage.setItem('dashboardWidgetSettings', JSON.stringify(newSettings));
  };

  const resetLayout = () => {
    const defaultLayout = tiles.map((tile, idx) => ({
      x: (idx % 4) * 3,
      y: Math.floor(idx / 4) * 3,
      w: 3,
      h: 3,
      i: tile.id,
      static: false
    }));
    setLayout(defaultLayout);
    localStorage.setItem('dashboardLayout', JSON.stringify(defaultLayout));
  };

  return (
    <div className="resizable-dashboard-wrapper">
      {/* Header Controls */}
      <div className="dashboard-controls">
        <button
          className="edit-toggle-btn"
          onClick={() => onEditModeChange(!isEditMode)}
        >
          {isEditMode ? '✓ Done Editing' : '✏️ Edit Layout'}
        </button>
        {isEditMode && (
          <button
            className="reset-layout-btn"
            onClick={resetLayout}
            title="Reset to default layout"
          >
            ↺ Reset Layout
          </button>
        )}
      </div>

      {/* Grid Layout */}
      <GridLayout
        className="dashboard-grid-layout"
        layout={layout}
        onLayoutChange={handleLayoutChange}
        width={1200}
        cols={12}
        rowHeight={50}
        isDraggable={isEditMode}
        isResizable={isEditMode}
        compactType="vertical"
        preventCollision={false}
        useCSSTransforms={true}
        containerPadding={[10, 10]}
        margin={[10, 10]}
      >
        {tiles.map((tile) => (
          <div
            key={tile.id}
            className={`dashboard-tile-container ${isEditMode ? 'edit-mode' : ''}`}
            data-grid-item={tile.id}
          >
            <div className="dashboard-tile-header">
              <h3 className="tile-title">{tile.title}</h3>
              {isEditMode && (
                <button
                  className="tile-settings-btn"
                  onClick={() => console.log(`Open settings for ${tile.id}`)}
                  title="Configure tile content"
                >
                  ⚙️
                </button>
              )}
              {!isEditMode && <div className="tile-drag-handle">⋮⋮</div>}
            </div>
            <div className="dashboard-tile-content">
              {tile.render ? tile.render(widgetSettings[tile.id]) : null}
            </div>
          </div>
        ))}
      </GridLayout>
    </div>
  );
};

export default ResizableDashboard;
