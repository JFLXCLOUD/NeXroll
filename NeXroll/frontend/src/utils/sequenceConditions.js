import { ratingSummary } from './trailerRatings';
import { audioLabel } from './audioFormats';
import { useCallback, useEffect, useState } from 'react';

/**
 * Sequence block conditions (Sequence Builder, Advanced mode).
 *
 * A block may carry `condition` ({match, rules}) and `otherwise` (a block to
 * play in its place when the condition is not met). The backend's
 * sequence_conditions.py is the authority on what they mean; this file only
 * describes and defaults them for the UI.
 */

// `playback` rules need to know what is about to play. Only the Jellyfin and
// Emby plugin can tell NeXroll that; Plex applies one preroll list to every
// movie, so on Plex those rules count as not met and the Otherwise plays.
export const RULE_KINDS = [
  { value: 'trailers_available', label: 'Trailers are available', short: 'Trailers available', playback: false },
  { value: 'time_window', label: 'Time of day', short: 'Time of day', playback: false },
  { value: 'genre', label: 'Genre of what is playing (Jellyfin & Emby)', short: 'Genre (Jellyfin & Emby)', playback: true },
  { value: 'audio_format', label: 'Stored audio format (Jellyfin & Emby)', short: 'Audio format (Jellyfin & Emby)', playback: true },
  { value: 'media_type', label: 'Movie or episode (Jellyfin & Emby)', short: 'Media type (Jellyfin & Emby)', playback: true },
];

export const isPlaybackRule = (kind) => !!(RULE_KINDS.find(k => k.value === kind) || {}).playback;

/** True when a condition has a rule only Jellyfin and Emby can answer. */
export const needsPlaybackInfo = (condition) =>
  !!(condition && Array.isArray(condition.rules) && condition.rules.some(rule => rule && isPlaybackRule(rule.kind)));

export const WEEKDAYS = [
  { value: 'monday', short: 'Mon' },
  { value: 'tuesday', short: 'Tue' },
  { value: 'wednesday', short: 'Wed' },
  { value: 'thursday', short: 'Thu' },
  { value: 'friday', short: 'Fri' },
  { value: 'saturday', short: 'Sat' },
  { value: 'sunday', short: 'Sun' },
];

const SOURCE_WORDS = { both: 'movie or TV', movies: 'movie', tv: 'TV' };

export const defaultRule = (kind = 'trailers_available') => {
  if (kind === 'media_type') return { kind, value: 'movie' };
  if (kind === 'genre') return { kind, values: [] };
  if (kind === 'audio_format') return { kind, track: 'default', values: [] };
  if (kind === 'time_window') return { kind, start: '18:00', end: '23:00', days: [] };
  return { kind: 'trailers_available', source: 'both', min: 1 };
};

export const defaultCondition = () => ({ match: 'all', rules: [defaultRule()] });

export const hasCondition = (block) =>
  !!(block && block.condition && Array.isArray(block.condition.rules) && block.condition.rules.length > 0);

export const blocksHaveConditions = (blocks) => Array.isArray(blocks) && blocks.some(hasCondition);

export const describeRule = (rule) => {
  if (!rule) return '';
  const not = !!rule.negate;
  switch (rule.kind) {
    case 'trailers_available': {
      if (rule.pool === 'block') return `${not ? 'fewer than' : 'at least'} ${rule.min || 1} trailer(s) can play in this/next trailer block`;
      const min = Math.max(parseInt(rule.min, 10) || 1, 1);
      const base = rule.pool === 'library' ? 'library' : (SOURCE_WORDS[rule.source] || SOURCE_WORDS.both);
      const filters = [ratingSummary(rule), ...(rule.pool === 'library' && rule.genres?.length ? [rule.genres.join(' / ')] : [])].filter(Boolean).join('; ');
      const kind = filters ? `${base} (${filters})` : base;
      if (not) {
        return min === 1 ? `no ${kind} trailers are available` : `fewer than ${min} ${kind} trailers are available`;
      }
      return min === 1 ? `a ${kind} trailer is available` : `at least ${min} ${kind} trailers are available`;
    }
    case 'media_type':
      return `${not ? 'not ' : ''}playing ${rule.value === 'episode' ? 'a TV episode' : 'a movie'}`;
    case 'audio_format': {
      const values = Array.isArray(rule.values) ? rule.values : [];
      const subject = rule.track === 'any' ? 'any stored audio track' : 'the stored default audio track';
      return `${not ? 'no match for ' : ''}${subject}: ${values.map(audioLabel).join(' or ') || 'choose a format'}`;
    }
    case 'genre': {
      const values = Array.isArray(rule.values) ? rule.values : [];
      if (!values.length) return 'a genre is chosen';
      return `the genre is ${not ? 'not ' : ''}${values.join(' or ')}`;
    }
    case 'time_window': {
      const days = Array.isArray(rule.days) && rule.days.length
        ? ` on ${rule.days.map(d => (WEEKDAYS.find(w => w.value === d) || {}).short || d).join(', ')}`
        : '';
      return `${not ? 'not ' : ''}between ${rule.start || '?'} and ${rule.end || '?'}${days}`;
    }
    default:
      return 'an unknown rule';
  }
};

export const describeCondition = (condition) => {
  const rules = (condition && Array.isArray(condition.rules)) ? condition.rules : [];
  if (!rules.length) return 'always';
  const joiner = condition.match === 'any' ? ' or ' : ' and ';
  return rules.map(describeRule).join(joiner);
};

export const describeOtherwise = (otherwise, getCategoryName) => {
  if (!otherwise) return 'the block is skipped';
  if (otherwise.type === 'random' || otherwise.type === 'sequential') {
    const name = getCategoryName ? getCategoryName(otherwise.category_id) : 'a category';
    const count = otherwise.count || 1;
    return `${count} preroll${count === 1 ? '' : 's'} from ${name} play instead`;
  }
  if (otherwise.type === 'nexup_trailers') {
    const count = otherwise.count || 1;
    return `${count} NeX-Up trailer${count === 1 ? '' : 's'} play instead`;
  }
  if (otherwise.type === 'library_trailers') {
    const count = otherwise.count || 1;
    return `${count} library trailer${count === 1 ? '' : 's'} play instead`;
  }
  if (otherwise.type === 'fixed') return 'specific prerolls play instead';
  return 'another block plays instead';
};

export const OTHERWISE_CHOICES = [
  { value: 'skip', label: 'Skip this block' },
  { value: 'random', label: 'Play prerolls from a category' },
  { value: 'nexup_trailers', label: 'Play NeX-Up trailers' },
  { value: 'library_trailers', label: 'Play library trailers' },
];

export const otherwiseChoiceOf = (otherwise) => {
  if (!otherwise) return 'skip';
  if (otherwise.type === 'nexup_trailers' || otherwise.type === 'library_trailers') return otherwise.type;
  return 'random';
};

export const otherwiseForChoice = (choice, categories = []) => {
  if (choice === 'random') {
    const first = [...categories].sort((a, b) => a.name.localeCompare(b.name))[0];
    return { type: 'random', category_id: first ? first.id : null, count: 1 };
  }
  if (choice === 'nexup_trailers') return { type: 'nexup_trailers', source: 'both', count: 1, mode: 'random' };
  if (choice === 'library_trailers') return { type: 'library_trailers', count: 1, mode: 'random' };
  return null;
};

/** A block's condition state after its rules change; no rules means no condition. */
export const withRules = (condition, otherwise, rules) => (
  rules.length
    ? { condition: { match: 'all', ...condition, rules }, otherwise }
    : { condition: null, otherwise: null }
);

/** Summary sentence shown under a condition, e.g. "Plays only when ... Otherwise, ...". */
export const describeBlockCondition = (condition, otherwise, getCategoryName) => (
  `Plays ${condition && condition.match === 'any' ? 'when' : 'only when'} ${describeCondition(condition)}. `
  + `Otherwise, ${describeOtherwise(otherwise, getCategoryName)}.`
);

// Per-browser builder preferences, shared by every builder on the page.
const useStoredChoice = (key, allowed, fallback) => {
  const [value, setValue] = useState(() => {
    try {
      const saved = window.localStorage.getItem(key);
      return allowed.includes(saved) ? saved : fallback;
    } catch (e) {
      return fallback;
    }
  });
  const setChoice = useCallback((next) => {
    setValue(next);
    try {
      window.localStorage.setItem(key, next);
    } catch (e) {
      // Storage unavailable (private window); the choice just won't persist.
    }
  }, [key]);
  return [value, setChoice];
};

const BUILDER_MODES = ['simple', 'advanced'];
const BUILDER_VIEWS = ['list', 'flow'];

/** Simple / Advanced: Advanced adds IF/THEN conditions to blocks. */
export const useBuilderMode = () => useStoredChoice('nexroll.sequenceBuilder.mode', BUILDER_MODES, 'simple');

/** List / Flow: Flow draws the sequence as a node workflow. */
export const useBuilderView = () => useStoredChoice('nexroll.sequenceBuilder.view', BUILDER_VIEWS, 'list');

// Genre names from the connected Jellyfin/Emby libraries, fetched once per
// page load and shared by every genre picker.
let libraryGenresPromise = null;

export const useLibraryGenres = () => {
  const [genres, setGenres] = useState([]);
  useEffect(() => {
    let active = true;
    if (!libraryGenresPromise) {
      if (typeof fetch !== 'function') return undefined;
      libraryGenresPromise = fetch('/sequences/genres')
        .then(res => (res.ok ? res.json() : { genres: [] }))
        .then(data => data.genres || [])
        .catch(() => { libraryGenresPromise = null; return []; });
    }
    libraryGenresPromise.then(list => { if (active) setGenres(list); });
    return () => { active = false; };
  }, []);
  return genres;
};

/** Genres named anywhere in a sequence's genre rules, for the preview picker. */
export const genresInSequence = (blocks) => {
  const seen = new Map();
  (blocks || []).forEach(block => {
    ((block && block.condition && block.condition.rules) || []).forEach(rule => {
      if (rule && rule.kind === 'genre') {
        (rule.values || []).forEach(v => { if (!seen.has(String(v).toLowerCase())) seen.set(String(v).toLowerCase(), v); });
      }
    });
  });
  return [...seen.values()];
};
