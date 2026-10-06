import { youtubeThumbnail, youtubeVideoId } from './youtube';

describe('youtubeVideoId', () => {
  test.each([
    ['https://www.youtube.com/watch?v=dQw4w9WgXcQ', 'dQw4w9WgXcQ'],
    ['https://youtube.com/watch?feature=share&v=dQw4w9WgXcQ&t=10', 'dQw4w9WgXcQ'],
    ['https://m.youtube.com/watch?v=dQw4w9WgXcQ', 'dQw4w9WgXcQ'],
    ['https://youtu.be/dQw4w9WgXcQ?si=abc', 'dQw4w9WgXcQ'],
    ['https://www.youtube.com/shorts/dQw4w9WgXcQ', 'dQw4w9WgXcQ'],
    ['https://www.youtube.com/embed/dQw4w9WgXcQ', 'dQw4w9WgXcQ'],
    ['youtube.com/watch?v=dQw4w9WgXcQ', 'dQw4w9WgXcQ'],
    ['  https://youtu.be/dQw4w9WgXcQ  ', 'dQw4w9WgXcQ'],
  ])('finds the video in %s', (url, id) => {
    expect(youtubeVideoId(url)).toBe(id);
  });

  test.each([
    [''],
    [null],
    ['https://vimeo.com/123456789'],
    ['https://www.youtube.com/channel/UCabcdefghijk'],
    ['https://www.youtube.com/watch?v=short'],
    ['https://notyoutube.com/watch?v=dQw4w9WgXcQ'],
  ])('ignores %s', (url) => {
    expect(youtubeVideoId(url)).toBeNull();
  });

  test('thumbnail', () => {
    expect(youtubeThumbnail('dQw4w9WgXcQ')).toBe('https://i.ytimg.com/vi/dQw4w9WgXcQ/mqdefault.jpg');
    expect(youtubeThumbnail(null)).toBe('');
  });
});
