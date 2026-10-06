// The 11-character video ID in a YouTube link (watch, youtu.be, Shorts, embed,
// live, music), or null when the text isn't a YouTube video link.
export const youtubeVideoId = (url) => {
  const text = String(url || '').trim();
  const match = text.match(
    /^(?:https?:\/\/)?(?:www\.|m\.|music\.)?(?:youtube\.com\/(?:watch\?(?:[^#]*&)?v=|shorts\/|embed\/|live\/|v\/)|youtu\.be\/)([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])/i
  );
  return match ? match[1] : null;
};

// A small thumbnail YouTube serves for every video, to show what will download.
export const youtubeThumbnail = (id) => (id ? `https://i.ytimg.com/vi/${id}/mqdefault.jpg` : '');
