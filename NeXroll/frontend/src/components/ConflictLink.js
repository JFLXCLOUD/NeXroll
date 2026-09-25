import React from 'react';

export default function ConflictLink({ onOpen, children, className = '', ...props }) {
  return <a {...props} href="#/schedules/conflicts" className={`nx-conflict-link nx-no-drag ${className}`}
    onPointerDown={e => e.stopPropagation()} onClick={e => { e.preventDefault(); e.stopPropagation(); onOpen(); }}>
    {children}
  </a>;
}
