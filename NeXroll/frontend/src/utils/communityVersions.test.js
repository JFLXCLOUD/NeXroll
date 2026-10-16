import { initialVersionPicks, platformLabel, rowVersions, versionView, wantedVersions } from './communityVersions';

const row = {
  id: 'p', title: 'Adult Swim',
  versions: [
    { id: 'p', platform: 'plex' },
    { id: 'j', platform: 'jellyfin' },
    { id: 'e', platform: 'emby' },
  ],
};
const ids = list => list.map(v => v.id);

test('a row without versions stands for itself', () => {
  const single = { id: 'x', title: 'Solo' };
  expect(rowVersions(single)).toEqual([single]);
  expect(rowVersions(null)).toEqual([]);
  expect(ids(wantedVersions(single, ['plex']))).toEqual(['x']);
});

test('the versions for every connected server are wanted', () => {
  expect(ids(wantedVersions(row, ['plex']))).toEqual(['p']);
  expect(ids(wantedVersions(row, ['jellyfin', 'plex']))).toEqual(['p', 'j']);
  expect(ids(wantedVersions(row, ['plex', 'jellyfin', 'emby']))).toEqual(['p', 'j', 'e']);
});

test('with no matching or connected server the leading version is wanted', () => {
  expect(ids(wantedVersions(row, []))).toEqual(['p']);
  const noEmby = { ...row, versions: row.versions.slice(0, 2) };
  expect(ids(wantedVersions(noEmby, ['emby']))).toEqual(['p']);
});

test('the dialog ticks wanted versions not yet downloaded, or the one clicked', () => {
  const downloaded = v => v.id === 'p';
  expect(initialVersionPicks(row, ['plex', 'jellyfin'], downloaded)).toEqual(['j']);
  expect(initialVersionPicks(row, ['plex'], downloaded)).toEqual([]);
  expect(initialVersionPicks(row, ['plex'], downloaded, 'e')).toEqual(['e']);
});

test('platform labels', () => {
  expect(platformLabel('jellyfin')).toBe('Jellyfin');
  expect(platformLabel(undefined)).toBe('Version');
});

test('a preview shows the chosen version with the row around it', () => {
  const grouped = {
    id: 'p', title: 'Adult Swim', creator: 'A', category: 'Community', url: 'u-p', duration: 20,
    versions: [
      { id: 'p', platform: 'plex', title: 'Adult Swim Plex', url: 'u-p', duration: 20 },
      { id: 'j', platform: 'jellyfin', title: 'Adult Swim Jellyfin', url: 'u-j', duration: 17 },
    ],
  };
  const shown = versionView(grouped, 'j');
  expect([shown.id, shown.url, shown.title, shown.duration]).toEqual(['j', 'u-j', 'Adult Swim Jellyfin', 17]);
  expect([shown.creator, shown.category, shown.rowId, shown.rowTitle]).toEqual(['A', 'Community', 'p', 'Adult Swim']);
  expect(shown.versions).toBe(grouped.versions);
  expect(versionView(grouped, 'missing').id).toBe('p');
  expect(versionView(grouped, undefined).id).toBe('p');
  const single = { id: 'x' };
  expect(versionView(single, 'j')).toBe(single);
  expect(versionView(null, 'j')).toBe(null);
});
