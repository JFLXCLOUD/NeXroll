// Length filter for Community Prerolls. Bounds are whole seconds and inclusive
// on the backend, compared with the length as displayed, so "30 seconds or
// less" keeps a 30.4 s preroll that the list shows as 0:30.
export const COMMUNITY_LENGTH_PRESETS = [
  { value: '', label: 'Any length' },
  { value: 'le15', label: '15 seconds or less', max: 15 },
  { value: 'le30', label: '30 seconds or less', max: 30 },
  { value: 'le60', label: '1 minute or less', max: 60 },
  { value: '60to120', label: '1 to 2 minutes', min: 60, max: 120 },
  { value: 'over120', label: 'Over 2 minutes', min: 121 },
  { value: 'custom', label: 'Custom range…' },
];

const toSeconds = (text) => {
  if (text === null || text === undefined || String(text).trim() === '') return null;
  const value = Number(text);
  return Number.isFinite(value) && value >= 0 ? Math.round(value) : null;
};

// { min, max } for the search request; either may be null (no bound).
export function communityLengthBounds(preset, customMin, customMax) {
  if (preset === 'custom') {
    let min = toSeconds(customMin);
    let max = toSeconds(customMax);
    if (min !== null && max !== null && min > max) [min, max] = [max, min];
    return { min, max };
  }
  const found = COMMUNITY_LENGTH_PRESETS.find(p => p.value === preset);
  return { min: found?.min ?? null, max: found?.max ?? null };
}

export function appendCommunityLengthParams(params, preset, customMin, customMax) {
  const { min, max } = communityLengthBounds(preset, customMin, customMax);
  if (min !== null) params.append('min_duration', min);
  if (max !== null) params.append('max_duration', max);
  return min !== null || max !== null;
}

// 0:12, 1:05, 12:30 - rounded the same way the backend rounds for filtering.
export function formatPrerollLength(seconds) {
  const value = Number(seconds);
  if (seconds === null || seconds === undefined || !Number.isFinite(value) || value <= 0) return null;
  const whole = Math.round(value);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`;
}
