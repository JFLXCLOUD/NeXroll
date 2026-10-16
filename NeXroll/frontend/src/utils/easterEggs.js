// Easter eggs. All of them stay in the browser: nothing here touches a media
// server, a schedule or a setting, apart from remembering which secret themes
// someone has unlocked.

// Up Up Down Down Left Right Left Right B A.
export const KONAMI = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'b', 'a'];

// The last keys pressed, newest last, never longer than the code.
export function pushKey(history, key) {
  const k = typeof key === 'string' && key.length === 1 ? key.toLowerCase() : key;
  return [...history, k].slice(-KONAMI.length);
}

export function isKonami(history) {
  return history.length === KONAMI.length && history.every((k, i) => k === KONAMI[i]);
}

// Typing in a field must never trigger anything.
export function isTypingTarget(target) {
  if (!target) return false;
  const tag = String(target.tagName || '').toLowerCase();
  return tag === 'input' || tag === 'textarea' || tag === 'select' || Boolean(target.isContentEditable);
}

// Movie lines that work in the sidebar search. `id` is the page it opens
// (null = just the reply); `unlock` names a secret theme it unlocks.
export const MOVIE_QUOTES = [
  { quote: 'show me the money', id: 'settings/storage', label: 'Storage', reply: 'Every byte, accounted for.' },
  { quote: "you're gonna need a bigger boat", id: 'settings/storage', label: 'Storage', reply: "Here's how full the hold is." },
  { quote: "i'll be back", id: 'settings/backup', label: 'Backup & Restore', reply: 'And so will your settings.' },
  { quote: "there's no place like home", id: 'dashboard', label: 'Dashboard', reply: 'Click your heels.' },
  { quote: "you can't handle the truth", id: 'settings/logs', label: 'Logs', reply: 'The whole truth is in app.log.' },
  { quote: 'houston we have a problem', id: 'settings/system', label: 'System', reply: 'Diagnostics are this way.' },
  { quote: 'play it again sam', id: 'schedules', label: 'My Schedules', reply: 'As often as you like, on a schedule.' },
  { quote: 'rosebud', id: null, label: 'Rosebud', reply: 'It was a sled.' },
  { quote: 'drive in', id: 'settings', label: 'Drive-In theme', reply: 'Unlocked. Pick it under Theme.', unlock: 'drivein' },
];

const normalize = (text) => String(text || '')
  .toLowerCase()
  .replace(/[‘’']/g, '')
  .replace(/[^a-z0-9]+/g, ' ')
  .trim();

// The quote a search box is typing, once most of it is there (so the joke
// doesn't spoil itself on the first letters).
export function matchMovieQuote(query) {
  const q = normalize(query);
  if (q.length < 4) return null;
  const compact = q.replace(/ /g, '');
  for (const entry of MOVIE_QUOTES) {
    const quote = normalize(entry.quote);
    if (q === quote || compact === quote.replace(/ /g, '')) return entry;
    if (quote.startsWith(q) && q.length >= Math.ceil(quote.length * 0.7)) return entry;
  }
  return null;
}

// Secret themes someone has unlocked, kept in this browser.
const SECRET_KEY = 'nx_secret_themes';

export function readSecretThemes(storage = (typeof window !== 'undefined' ? window.localStorage : null)) {
  try {
    const list = JSON.parse(storage?.getItem(SECRET_KEY) || '[]');
    return Array.isArray(list) ? list.filter(id => typeof id === 'string') : [];
  } catch {
    return [];
  }
}

export function saveSecretThemes(list, storage = (typeof window !== 'undefined' ? window.localStorage : null)) {
  try { storage?.setItem(SECRET_KEY, JSON.stringify(list)); } catch { /* private window: unlock lasts this session */ }
}
