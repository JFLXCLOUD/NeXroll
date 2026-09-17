/**
 * Estimate how long a sequence runs and how much it can vary.
 *
 * The builder used to report `blocks.length * 2` minutes and
 * `blocks.length * 12` variations. Both numbers were invented: two fixed clips
 * totalling 23 seconds were announced as "4m 10s", and a single deterministic
 * block claimed "12 variations". Numbers presented that confidently have to be
 * derived from the actual content or not shown at all.
 *
 * Durations come from the library where we know them. Where a block's contents
 * are decided at playback time (a NeX-Up trailer, a generated preroll) we fall
 * back to a typical length and mark the whole estimate approximate, so the UI
 * can say "about" rather than implying it measured something.
 */

// Typical lengths for content that does not exist yet at build time.
export const ASSUMED = {
  preroll: 30,   // a preroll whose duration the library has not recorded
  trailer: 90,   // a NeX-Up trailer
  generated: 30, // a Coming Soon list or dynamic preroll
};

function durationOf(prerolls, id) {
  const found = prerolls.find(p => p.id === id);
  const seconds = Number(found?.duration);
  return Number.isFinite(seconds) && seconds > 0
    ? { seconds, known: true }
    : { seconds: ASSUMED.preroll, known: false };
}

function inCategory(prerolls, categoryId) {
  return prerolls.filter(p => p.category_id === categoryId);
}

/** Ordered selections of `k` from `n` - how many ways a random block can play. */
function permutations(n, k) {
  if (k <= 0 || n <= 0 || k > n) return 1;
  let total = 1;
  for (let i = 0; i < k; i += 1) total *= (n - i);
  return total;
}

/**
 * @returns {{seconds:number, variations:number, exact:boolean, blocks:number}}
 *   `exact` is false when any part of the estimate rested on an assumption.
 *   `variations` is 1 for a sequence that plays identically every time.
 */
export function estimateSequence(blocks = [], prerolls = []) {
  let seconds = 0;
  let variations = 1;
  let exact = true;

  blocks.forEach(block => {
    switch (block?.type) {
      case 'preroll': {
        const d = durationOf(prerolls, block.preroll_id);
        seconds += d.seconds;
        if (!d.known) exact = false;
        break;
      }
      case 'fixed': {
        (block.preroll_ids || []).forEach(id => {
          const d = durationOf(prerolls, id);
          seconds += d.seconds;
          if (!d.known) exact = false;
        });
        break;
      }
      case 'sequential': {
        const pool = inCategory(prerolls, block.category_id);
        pool.forEach(p => {
          const d = durationOf(prerolls, p.id);
          seconds += d.seconds;
          if (!d.known) exact = false;
        });
        if (!pool.length) exact = false;
        break;
      }
      case 'random': {
        const pool = inCategory(prerolls, block.category_id);
        const count = Math.max(1, Number(block.count) || 1);
        if (pool.length) {
          const avg = pool.reduce((sum, p) => sum + (Number(p.duration) || ASSUMED.preroll), 0) / pool.length;
          seconds += avg * count;
          if (pool.some(p => !Number(p.duration))) exact = false;
          // Picking from a pool is the only thing that genuinely varies.
          variations *= permutations(pool.length, Math.min(count, pool.length));
        } else {
          seconds += ASSUMED.preroll * count;
          exact = false;
        }
        break;
      }
      case 'nexup_trailers': {
        const count = Math.max(1, Number(block.count) || 2);
        seconds += count * ASSUMED.trailer;
        exact = false; // the trailers are chosen when it plays
        break;
      }
      case 'coming_soon_list':
      case 'dynamic_preroll': {
        // A generated block names one specific file and plays it every time -
        // its own caption says so. When the library knows that file's duration
        // there is nothing to estimate, and reporting "~30s" for a clip we have
        // measured was reported as the estimate still being wrong.
        const named = block.filename
          ? prerolls.find(p => p.filename === block.filename)
          : null;
        const measured = Number(named?.duration);
        if (Number.isFinite(measured) && measured > 0) {
          seconds += measured;
        } else {
          seconds += ASSUMED.generated;
          exact = false;
        }
        break;
      }
      case 'separator':
        break;
      default:
        // An unrecognised block still occupies time we cannot account for.
        exact = false;
        break;
    }
  });

  return { seconds: Math.round(seconds), variations, exact, blocks: blocks.length };
}

/** "23s", "1m 05s", "1h 02m" - never a bare rounded-up minute count. */
export function formatDuration(seconds) {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  if (total < 60) return `${total}s`;
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hours) return `${hours}h ${String(minutes).padStart(2, '0')}m`;
  return `${minutes}m ${String(secs).padStart(2, '0')}s`;
}

/** What the builder header shows. Empty sequences get an em dash, not a guess. */
export function describeEstimate(blocks = [], prerolls = []) {
  if (!blocks.length) {
    return { blocks: '0', duration: '—', variations: '—', plays: 'Add a block to see an estimate' };
  }
  const { seconds, variations, exact } = estimateSequence(blocks, prerolls);
  return {
    blocks: String(blocks.length),
    duration: (exact ? '' : '~') + formatDuration(seconds),
    variations: variations > 1 ? variations.toLocaleString() : '1',
    plays: variations > 1
      ? 'Shuffles between runs'
      : 'Plays the same every time',
  };
}
