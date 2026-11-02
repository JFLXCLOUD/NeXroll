import { MAX_UPLOAD_BYTES, fileKey, isVideoFile, mergeFiles, pendingFiles, summarizeUpload, uploadErrorMessage } from './uploadQueue';

const file = (name, size = 1000, type = 'video/mp4', lastModified = 1) => ({ name, size, type, lastModified });

test('video files are recognised by type or by extension', () => {
  expect(isVideoFile(file('a.mp4'))).toBe(true);
  expect(isVideoFile(file('b.MKV', 1, ''))).toBe(true);
  expect(isVideoFile(file('c.ts', 1, 'text/vnd.trolltech.linguist'))).toBe(true);
  expect(isVideoFile(file('notes.txt', 1, 'text/plain'))).toBe(false);
});

test('mergeFiles adds new files, skips repeats and reports non-videos', () => {
  const a = file('a.mp4');
  const { files, notVideo, repeated } = mergeFiles([a], [a, file('b.mp4'), file('cover.jpg', 5, 'image/jpeg')]);
  expect(files.map(f => f.name)).toEqual(['a.mp4', 'b.mp4']);
  expect(notVideo).toEqual(['cover.jpg']);
  expect(repeated).toBe(1);
});

test('two files with the same name from different folders both stay', () => {
  const { files } = mergeFiles([], [file('intro.mp4', 10), file('intro.mp4', 20)]);
  expect(files).toHaveLength(2);
  expect(fileKey(files[0])).not.toBe(fileKey(files[1]));
});

test('pendingFiles leaves out finished and oversized files but retries failed ones', () => {
  const done = file('done.mp4');
  const skipped = file('skipped.mp4');
  const failed = file('failed.mp4');
  const fresh = file('fresh.mp4');
  const huge = file('huge.mp4', MAX_UPLOAD_BYTES + 1);
  const progress = {
    [fileKey(done)]: { status: 'completed' },
    [fileKey(skipped)]: { status: 'skipped' },
    [fileKey(failed)]: { status: 'error', error: 'x' },
  };
  expect(pendingFiles([done, skipped, failed, fresh, huge], progress).map(f => f.name)).toEqual(['failed.mp4', 'fresh.mp4']);
  expect(summarizeUpload([done, skipped, failed, fresh], progress)).toEqual({ completed: 1, skipped: 1, error: 1 });
});

test('uploadErrorMessage reads the server detail and falls back to the status', () => {
  expect(uploadErrorMessage(400, JSON.stringify({ detail: 'Selected category does not exist' }))).toBe('Selected category does not exist');
  expect(uploadErrorMessage(502, '<html>Bad gateway</html>')).toBe('Upload failed (HTTP 502)');
  expect(uploadErrorMessage(413, '')).toMatch(/500 MB/);
  expect(uploadErrorMessage(0, '')).toMatch(/Network error/);
});
