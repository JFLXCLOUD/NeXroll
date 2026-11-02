/**
 * Library > Add Prerolls upload list helpers.
 *
 * Files are keyed by name, size and modified time, so picking or dropping the
 * same file twice doesn't queue it twice, and two different files that share a
 * name (from two folders) keep separate rows and progress.
 */

// Matches MAX_PREROLL_UPLOAD_SIZE in backend/preroll_files.py. The server reads
// a whole file before it can refuse it, so oversized files are left out here.
export const MAX_UPLOAD_BYTES = 500 * 1024 * 1024;

export const VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.ts', '.mpg', '.mpeg'];

export const fileKey = (file) => `${file?.name}:${file?.size}:${file?.lastModified}`;

export const isVideoFile = (file) => {
  const name = String(file?.name || '').toLowerCase();
  return String(file?.type || '').startsWith('video/') || VIDEO_EXTENSIONS.some(ext => name.endsWith(ext));
};

export const isTooLarge = (file) => (Number(file?.size) || 0) > MAX_UPLOAD_BYTES;

/**
 * Adds picked or dropped files to the list. Returns the new list plus what was
 * left out: `notVideo` (names) and `repeated` (already listed).
 */
export const mergeFiles = (existing, incoming) => {
  const files = [...(existing || [])];
  const seen = new Set(files.map(fileKey));
  const notVideo = [];
  let repeated = 0;
  Array.from(incoming || []).forEach(file => {
    if (!isVideoFile(file)) { notVideo.push(file.name); return; }
    const key = fileKey(file);
    if (seen.has(key)) { repeated += 1; return; }
    seen.add(key);
    files.push(file);
  });
  return { files, notVideo, repeated };
};

// Statuses that need no further upload. 'error' stays retryable.
const FINISHED = new Set(['completed', 'skipped']);

export const isFinished = (status) => FINISHED.has(status?.status);

/** Files the Upload button would send: not finished and within the size limit. */
export const pendingFiles = (files, progress) =>
  (files || []).filter(file => !isFinished(progress?.[fileKey(file)]) && !isTooLarge(file));

export const summarizeUpload = (files, progress) => {
  const counts = { completed: 0, skipped: 0, error: 0 };
  (files || []).forEach(file => {
    const status = progress?.[fileKey(file)]?.status;
    if (status in counts) counts[status] += 1;
  });
  return counts;
};

/** Reads the server's error out of an XHR response; HTML error pages fall back to the status. */
export const uploadErrorMessage = (status, responseText) => {
  if (status === 413) return 'File too large. Maximum upload size is 500 MB.';
  try {
    const data = JSON.parse(responseText);
    const detail = data?.detail || data?.message;
    if (detail) return typeof detail === 'string' ? detail : JSON.stringify(detail);
  } catch (_) {
    // Not JSON (a proxy's error page, for instance).
  }
  return status ? `Upload failed (HTTP ${status})` : 'Network error. Check that NeXroll is still running.';
};

/**
 * Sends one file with XMLHttpRequest, which (unlike fetch) reports upload
 * progress. `onProgress(loaded)` fires while sending, `onSent()` once the
 * server has the whole file and is probing it and making the thumbnail.
 * Returns { promise, abort }.
 */
export const sendUpload = (url, formData, { onProgress, onSent } = {}) => {
  const xhr = new XMLHttpRequest();
  const promise = new Promise((resolve, reject) => {
    xhr.open('POST', url);
    xhr.upload.onprogress = (event) => { if (onProgress) onProgress(event.loaded); };
    xhr.upload.onload = () => { if (onSent) onSent(); };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        let data = {};
        try { data = JSON.parse(xhr.responseText); } catch (_) {}
        resolve(data);
      } else {
        reject(new Error(uploadErrorMessage(xhr.status, xhr.responseText)));
      }
    };
    xhr.onerror = () => reject(new Error(uploadErrorMessage(0, '')));
    xhr.onabort = () => {
      const error = new Error('Cancelled');
      error.cancelled = true;
      reject(error);
    };
    xhr.send(formData);
  });
  return { promise, abort: () => xhr.abort() };
};
