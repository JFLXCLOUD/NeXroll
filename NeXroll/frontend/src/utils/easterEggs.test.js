import {
  KONAMI, isKonami, isTypingTarget, matchMovieQuote, pushKey, readSecretThemes, saveSecretThemes,
} from './easterEggs';

const typeKeys = (keys, history = []) => keys.reduce((h, k) => pushKey(h, k), history);

test('the Konami code is recognized, with B and A in either case', () => {
  expect(isKonami(typeKeys(KONAMI))).toBe(true);
  expect(isKonami(typeKeys([...KONAMI.slice(0, 8), 'B', 'A']))).toBe(true);
});

test('extra keys before the code do not matter, a wrong key does', () => {
  expect(isKonami(typeKeys(['x', 'ArrowUp', ...KONAMI]))).toBe(true);
  expect(isKonami(typeKeys([...KONAMI.slice(0, 9), 'c']))).toBe(false);
  expect(isKonami(typeKeys(KONAMI.slice(0, 9)))).toBe(false);
});

test('typing in fields never counts', () => {
  expect(isTypingTarget({ tagName: 'INPUT' })).toBe(true);
  expect(isTypingTarget({ tagName: 'textarea' })).toBe(true);
  expect(isTypingTarget({ tagName: 'DIV', isContentEditable: true })).toBe(true);
  expect(isTypingTarget({ tagName: 'BUTTON' })).toBe(false);
  expect(isTypingTarget(null)).toBe(false);
});

test.each([
  ['Show me the money!', 'settings/storage'],
  ["I'll be back", 'settings/backup'],
  ['ill be back', 'settings/backup'],
  ['There’s no place like home', 'dashboard'],
  ["you're gonna need a bigger", 'settings/storage'],
  ['Houston, we have a problem.', 'settings/system'],
  ['ROSEBUD', null],
])('"%s" opens %s', (query, id) => {
  expect(matchMovieQuote(query)?.id).toBe(id);
});

test('drive-in unlocks the secret theme however it is written', () => {
  for (const q of ['drive-in', 'Drive In', 'drivein']) {
    expect(matchMovieQuote(q)?.unlock).toBe('drivein');
  }
});

test('the first few letters do not give a quote away', () => {
  expect(matchMovieQuote('show')).toBeNull();
  expect(matchMovieQuote('show me')).toBeNull();
  expect(matchMovieQuote('storage')).toBeNull();
  expect(matchMovieQuote('')).toBeNull();
});

test('unlocked secret themes are remembered, and bad storage is ignored', () => {
  const store = {};
  const storage = { getItem: k => store[k] ?? null, setItem: (k, v) => { store[k] = v; } };
  expect(readSecretThemes(storage)).toEqual([]);
  saveSecretThemes(['drivein'], storage);
  expect(readSecretThemes(storage)).toEqual(['drivein']);
  store.nx_secret_themes = '{not json';
  expect(readSecretThemes(storage)).toEqual([]);
  expect(readSecretThemes({ getItem: () => { throw new Error('blocked'); } })).toEqual([]);
});
