// A Community result row can stand for several platform versions of one
// preroll (row.versions, from the backend's group_versions). These helpers
// decide which of them a user needs: the versions for the servers they have
// connected, so someone running Plex and Jellyfin gets both.
export const PLATFORM_LABELS = { plex: 'Plex', jellyfin: 'Jellyfin', emby: 'Emby', universal: 'Universal' };

export const platformLabel = (platform) => PLATFORM_LABELS[platform] || platform || 'Version';

// Every file a row stands for: its versions, or the row itself.
export function rowVersions(row) {
  if (!row) return [];
  return Array.isArray(row.versions) && row.versions.length ? row.versions : [row];
}

// The versions this install wants: those for the connected servers, or the
// leading one (the backend puts the user's preference first) when none match.
export function wantedVersions(row, servers = []) {
  const versions = rowVersions(row);
  const mine = versions.filter(v => servers.includes(v.platform));
  return mine.length ? mine : versions.slice(0, 1);
}

// The row as one of its versions, for previews: that version's file, title,
// length and size, keeping the row's creator/category and its versions list.
// An unknown or missing id gives the leading version; a row without versions
// is returned as it is.
export function versionView(row, versionId) {
  if (!row || !Array.isArray(row.versions) || !row.versions.length) return row;
  const version = row.versions.find(v => v.id === versionId) || row.versions[0];
  return { ...row, ...version, rowId: row.id, rowTitle: row.title, versions: row.versions };
}

// What to tick when the download dialog opens: the wanted versions not yet
// downloaded, or the one version the user clicked.
export function initialVersionPicks(row, servers, isDownloaded, onlyId = null) {
  const versions = rowVersions(row);
  if (onlyId) return versions.filter(v => v.id === onlyId).map(v => v.id);
  return wantedVersions(row, servers).filter(v => !isDownloaded(v)).map(v => v.id);
}
