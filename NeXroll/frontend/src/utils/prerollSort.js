// Sorting for the preroll library view.
//
// Kept out of App.js so the ordering rules can be tested directly - the corner
// cases (unprobed durations, natural number ordering, stable paging) are easy to
// get subtly wrong and invisible until a user notices their library is shuffled.

// Each field carries its own direction wording, because a bare up/down arrow is
// ambiguous for dates and durations ("is up newest or oldest?").
export const PREROLL_SORT_FIELDS = [
  { value: 'added', label: 'Last added', desc: 'Newest first', asc: 'Oldest first' },
  { value: 'name', label: 'Name', desc: 'Z to A', asc: 'A to Z' },
  { value: 'duration', label: 'Duration', desc: 'Longest first', asc: 'Shortest first' },
];

export const DEFAULT_SORT_FIELD = 'added';
export const DEFAULT_SORT_DIRECTION = 'desc';

// Natural-order comparison so "bumper2" sorts before "bumper10" rather than
// after it, which is what plain string comparison would do.
const COLLATOR = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });

export const isSortField = (value) =>
  PREROLL_SORT_FIELDS.some(field => field.value === value);

export const sortFieldOrDefault = (value) =>
  (isSortField(value) ? value : DEFAULT_SORT_FIELD);

export const sortDirectionOrDefault = (value) =>
  (value === 'asc' ? 'asc' : DEFAULT_SORT_DIRECTION);

export const describeSort = (field, direction) => {
  const active = PREROLL_SORT_FIELDS.find(f => f.value === field) || PREROLL_SORT_FIELDS[0];
  return direction === 'asc' ? active.asc : active.desc;
};

const nameOf = (preroll) => preroll.display_name || preroll.filename || '';

const addedOf = (preroll) => {
  const parsed = Date.parse(preroll.upload_date || '');
  return Number.isNaN(parsed) ? 0 : parsed;
};

// null means "not known", which is different from zero-length.
const durationOf = (preroll) => {
  const value = Number(preroll.duration);
  return Number.isFinite(value) && value > 0 ? value : null;
};

/**
 * Order a list of prerolls. Returns a new array; the input is not mutated.
 *
 * Ties break on id so paging stays stable when two prerolls share a value -
 * common for duration, and for name across different categories.
 */
export function sortPrerolls(prerolls, field, direction) {
  const sortField = sortFieldOrDefault(field);
  const dir = sortDirectionOrDefault(direction) === 'asc' ? 1 : -1;

  return [...(prerolls || [])].sort((a, b) => {
    let cmp = 0;

    if (sortField === 'name') {
      cmp = COLLATOR.compare(nameOf(a), nameOf(b));
    } else if (sortField === 'duration') {
      const da = durationOf(a);
      const db = durationOf(b);
      // Prerolls whose duration was never probed sink to the bottom either way,
      // rather than masquerading as the shortest videos in the library.
      if (da === null || db === null) {
        if (da !== db) return da === null ? 1 : -1;
      } else {
        cmp = da - db;
      }
    } else {
      cmp = addedOf(a) - addedOf(b);
    }

    if (cmp !== 0) return cmp * dir;
    return (a.id || 0) - (b.id || 0);
  });
}
