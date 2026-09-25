import React from 'react';
import { hasRatingFilter, TRAILER_RATINGS } from '../utils/trailerRatings';

export default function TrailerRatingFilter({ value, onChange, includeTV = true }) {
  const selected = Array.isArray(value?.ratings) ? value.ratings : [];
  const enabled = hasRatingFilter(value);
  const ratings = TRAILER_RATINGS.filter(r => includeTV || !r.startsWith('TV-') || selected.includes(r));
  return <fieldset style={{ border: '1px solid var(--border-color)', borderRadius: 8, padding: 10, minWidth: 0, margin: '8px 0' }}>
    <legend style={{ fontSize: 13 }}>Age ratings</legend>
    <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 13 }}>
      <input type="checkbox" checked={enabled} onChange={e => onChange({ restrict_ratings: e.target.checked, ratings: e.target.checked ? selected : [] })} />
      Restrict age ratings
    </label>
    {enabled && <>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 12px', marginTop: 10 }}>
        {ratings.map(rating => <label key={rating} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12 }}>
          <input type="checkbox" checked={selected.includes(rating)} onChange={e => onChange({
            restrict_ratings: true,
            ratings: e.target.checked ? [...selected, rating] : selected.filter(r => r !== rating),
          })} />{rating}
        </label>)}
      </div>
      <p style={{ fontSize: 11, color: 'var(--text-secondary)', margin: '8px 0 0' }}>
        {selected.length ? 'Only the selected ratings can play. Missing ratings are excluded unless Unrated is selected.' : 'No ratings selected: no trailers will match.'}
        {' '}Ratings describe the film or show, not a separate review of the trailer. Older trailers receive ratings on the next NeX-Up sync.
      </p>
    </>}
  </fieldset>;
}
