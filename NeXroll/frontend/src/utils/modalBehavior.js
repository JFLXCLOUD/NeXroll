let bodyScrollLockCount = 0;
let bodyOverflowBeforeLock = '';

/**
 * Lock page scrolling while one or more dialogs are open. The reference count
 * prevents closing a nested dialog from re-enabling scroll behind its parent.
 */
export const lockBodyScroll = () => {
  if (typeof document === 'undefined' || !document.body) return () => {};

  if (bodyScrollLockCount === 0) {
    bodyOverflowBeforeLock = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
  }
  bodyScrollLockCount += 1;

  let released = false;
  return () => {
    if (released) return;
    released = true;
    bodyScrollLockCount = Math.max(0, bodyScrollLockCount - 1);
    if (bodyScrollLockCount === 0) {
      document.body.style.overflow = bodyOverflowBeforeLock;
      bodyOverflowBeforeLock = '';
    }
  };
};
