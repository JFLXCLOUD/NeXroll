// Community server URLs for the Change Server picker, the Community "Server"
// tile, the dashboard tile and previews. The server list and the choice of
// server live in backend/community_servers.py.

const trimUrl = (url) => String(url || '').trim().replace(/\/+$/, '');

// "https://home.prerolls.uk/" -> "home.prerolls.uk"
export const serverHost = (url) => trimUrl(url).replace(/^https?:\/\//i, '');

export const sameServer = (a, b) => Boolean(trimUrl(a)) && trimUrl(a).toLowerCase() === trimUrl(b).toLowerCase();

// Previews play from the server in use, as downloads do. Each index entry keeps
// the URL of the server the index was built from, which may be gone
// (usa.prerolls.uk since October 2026).
export const communityFileUrl = (item, serverUrl) => {
  const path = typeof item?.path === 'string' && item.path.startsWith('/') ? item.path : '';
  if (path && trimUrl(serverUrl)) return trimUrl(serverUrl) + path;
  return item?.url || item?.download_url || '';
};
