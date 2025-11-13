import React, { useEffect, useState } from 'react';

/**
 * RetroProgressBar - A subtle, minimal progress bar for indexing
 */
const RetroProgressBar = ({ progress, currentDir, filesFound, dirsVisited, message }) => {
  const [animatedProgress, setAnimatedProgress] = useState(0);
  
  // Smooth progress animation
  useEffect(() => {
    const target = Math.min(100, Math.max(0, progress || 0));
    const step = () => {
      setAnimatedProgress(prev => {
        const diff = target - prev;
        if (Math.abs(diff) < 0.5) return target;
        return prev + diff * 0.15;  // Smooth easing
      });
    };
    
    const timer = setInterval(step, 50);
    return () => clearInterval(timer);
  }, [progress]);
  
  return (
    <div style={styles.container}>
      {/* Progress bar */}
      <div style={styles.progressBarOuter}>
        <div 
          style={{
            ...styles.progressBarFill,
            width: `${animatedProgress}%`
          }}
        />
      </div>
      
      {/* Info text */}
      <div style={styles.infoRow}>
        <span style={styles.statusText}>
          {message || 'Scanning...'} {currentDir && `• ${currentDir}`}
        </span>
        <span style={styles.statsText}>
          {dirsVisited || 0} dirs • {filesFound || 0} files • {Math.floor(animatedProgress)}%
        </span>
      </div>
    </div>
  );
};

const styles = {
  container: {
    padding: '1rem 0',
    width: '100%',
  },
  progressBarOuter: {
    width: '100%',
    height: '6px',
    backgroundColor: 'rgba(0, 0, 0, 0.2)',
    borderRadius: '3px',
    overflow: 'hidden',
    marginBottom: '0.5rem',
    border: '1px solid var(--border-color)',
  },
  progressBarFill: {
    height: '100%',
    background: 'linear-gradient(90deg, #3b82f6, #2563eb)',
    transition: 'width 0.3s ease',
    borderRadius: '3px',
  },
  infoRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    fontSize: '0.85rem',
    color: 'var(--text-secondary)',
    gap: '1rem',
  },
  statusText: {
    flex: 1,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  statsText: {
    flexShrink: 0,
    fontWeight: '500',
  },
};

export default RetroProgressBar;
