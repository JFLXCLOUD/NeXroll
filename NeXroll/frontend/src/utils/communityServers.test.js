import { communityFileUrl, sameServer, serverHost } from './communityServers';

test('serverHost drops the scheme and trailing slashes', () => {
  expect(serverHost('https://home.prerolls.uk/')).toBe('home.prerolls.uk');
  expect(serverHost('http://192.168.1.5:8080')).toBe('192.168.1.5:8080');
  expect(serverHost('')).toBe('');
  expect(serverHost(null)).toBe('');
});

test('sameServer ignores case and trailing slashes', () => {
  expect(sameServer('https://Prerolls.uk/', 'https://prerolls.uk')).toBe(true);
  expect(sameServer('https://prerolls.uk', 'https://home.prerolls.uk')).toBe(false);
  expect(sameServer('', '')).toBe(false);
});

test('communityFileUrl plays from the server in use, not the one the index was built from', () => {
  const item = { path: '/Holidays/Christmas/Snow%20Day.mp4', url: 'https://usa.prerolls.uk/Holidays/Christmas/Snow%20Day.mp4' };
  expect(communityFileUrl(item, 'https://prerolls.uk/')).toBe('https://prerolls.uk/Holidays/Christmas/Snow%20Day.mp4');
  expect(communityFileUrl(item, 'https://home.prerolls.uk')).toBe('https://home.prerolls.uk/Holidays/Christmas/Snow%20Day.mp4');
});

test('communityFileUrl falls back to the stored URL without a server or a path', () => {
  const item = { path: '/Clips/a.mp4', url: 'https://usa.prerolls.uk/Clips/a.mp4' };
  expect(communityFileUrl(item, '')).toBe(item.url);
  expect(communityFileUrl({ url: 'https://x.example/a.mp4' }, 'https://prerolls.uk')).toBe('https://x.example/a.mp4');
  expect(communityFileUrl({ id: '_legacy_id', download_url: 'https://x.example/b.mp4' }, 'https://prerolls.uk')).toBe('https://x.example/b.mp4');
  expect(communityFileUrl(null, 'https://prerolls.uk')).toBe('');
});
