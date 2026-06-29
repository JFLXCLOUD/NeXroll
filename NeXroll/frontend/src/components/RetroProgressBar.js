import React from 'react';

/**
 * Indexing progress bar.
 *
 * The width is driven directly by the real `progress` value from the backend
 * (directories visited vs discovered) and glides via a single CSS transition —
 * no separate JS easing loop, which previously fought the transition and made
 * the bar feel jumpy/too fast. An indeterminate shimmer sits on top so the bar
 * always looks alive even between progress updates.
 */
const RetroProgressBar = ({ progress, currentDir, filesFound, dirsVisited, message }) => {
  const pct = Math.min(100, Math.max(0, Math.round(progress || 0)));

  return (
    <div className="nx-buildbar">
      <div className="nx-buildbar-track">
        <div className="nx-buildbar-fill" style={{ width: `${pct}%` }}>
          <span className="nx-buildbar-shimmer" aria-hidden="true" />
        </div>
      </div>
      <div className="nx-buildbar-info">
        <span className="nx-buildbar-status">
          {message || 'Scanning…'}{currentDir ? ` · ${currentDir}` : ''}
        </span>
        <span className="nx-buildbar-stats">
          {dirsVisited || 0} dirs · {filesFound || 0} files · {pct}%
        </span>
      </div>
    </div>
  );
};

export default RetroProgressBar;
