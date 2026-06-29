import React, { useEffect, useRef } from 'react';
import { CheckCircle, Info, X } from 'lucide-react';

/**
 * NeXroll v2 — Toast notifications
 *
 * Lightweight, themed, auto-dismissing notifications for success/info messages.
 * Errors, warnings, and confirmations still use the blocking styled dialog;
 * toasts are reserved for non-blocking "it worked" feedback.
 *
 * Props:
 *   toasts    [{ id, type: 'success'|'info', message }]
 *   onDismiss (id) => void
 */

const ICONS = {
  success: CheckCircle,
  info: Info,
};

function ToastItem({ toast, onDismiss }) {
  const timer = useRef(null);

  useEffect(() => {
    // Auto-dismiss; longer for longer messages.
    const len = (toast.message || '').length;
    const ms = Math.min(8000, Math.max(3000, 2000 + len * 40));
    timer.current = setTimeout(() => onDismiss(toast.id), ms);
    return () => clearTimeout(timer.current);
  }, [toast.id, toast.message, onDismiss]);

  const Icon = ICONS[toast.type] || Info;

  return (
    <div className={`nx-toast nx-toast-${toast.type || 'info'}`} role="status">
      <span className="nx-toast-icon"><Icon size={18} /></span>
      <span className="nx-toast-msg">{toast.message}</span>
      <button
        type="button"
        className="nx-toast-close"
        onClick={() => onDismiss(toast.id)}
        aria-label="Dismiss"
      >
        <X size={15} />
      </button>
    </div>
  );
}

function ToastHost({ toasts, onDismiss }) {
  if (!toasts || toasts.length === 0) return null;
  return (
    <div className="nx-toast-host" aria-live="polite">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

export default ToastHost;
