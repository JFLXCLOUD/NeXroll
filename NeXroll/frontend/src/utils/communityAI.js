// Community IDs retain the original catalog path after downloads and renames.
// Only that source identifies AI content; local names, tags and folders do not.
export function isAICommunitySource(communityId) {
  if (typeof communityId !== 'string' || !communityId.trim()) return false;
  let path = communityId.trim();
  if (/^https?:\/\//i.test(path)) {
    try { path = new URL(path).pathname; } catch { return false; }
  }
  const first = path.replace(/\\/g, '/').split('/').find(part => part.trim());
  if (!first) return false;
  try { return decodeURIComponent(first).trim().toLowerCase() === 'ai'; }
  catch { return false; }
}
