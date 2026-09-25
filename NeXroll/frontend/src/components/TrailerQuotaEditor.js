import React from 'react';

const RATINGS = ['G', 'PG', 'PG-13', 'R', 'NC-17', 'Unrated'];

export function TrailerQuotaReport({ entries = [], title = 'Current pool' }) {
  if (!entries.length) return null;
  return <div aria-label={title} style={{ marginTop: 12 }}>
    <strong>{title}</strong>
    {entries.map((entry, index) => <p key={index} style={{ fontSize: 12, margin: '8px 0' }}>
      <strong>{entry.values.join(' / ')}: {entry.available} / {entry.min}</strong>
      {' — '}{entry.shortfall ? `${entry.shortfall} more needed. ${entry.reason}` : 'Target met.'}
      {' '}Matching movies: {entry.matching_movies}.
    </p>)}
  </div>;
}

export default function TrailerQuotaEditor({ value = [], onChange, genres = [], report = [], disabled = false, standalone = false }) {
  const update = (index, patch) => onChange(value.map((rule, i) => i === index ? { ...rule, ...patch } : rule));
  return <section aria-label="Trailer pool targets" className={standalone ? 'nx-lt-targets' : undefined} style={standalone ? { minWidth: 0 } : { borderTop: '1px solid var(--border-color)', paddingTop: 14, marginTop: 14, minWidth: 0 }}>
    <strong className="nx-lt-section-title">Minimum trailer targets</strong>
    <p className="nx-ap-library-muted">Try to keep a mix of ratings and genres within your selection. A trailer can count toward several targets. Enabled local trailers count too, without using download slots. Targets never override your movie filters or download limits.</p>
    {value.map((rule, index) => {
      const choices = rule.kind === 'rating' ? RATINGS : [...new Set([...genres.map(g => typeof g === 'string' ? g : g.name), ...rule.values])];
      return <fieldset key={index} disabled={disabled} style={{ border: '1px solid var(--border-color)', borderRadius: 8, padding: 10, minWidth: 0, margin: '10px 0' }}>
        <legend>Target {index + 1}</legend>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <label>Match <select aria-label={`Target ${index + 1} type`} value={rule.kind} onChange={e => update(index, { kind: e.target.value, values: [] })}>
            <option value="rating">Age ratings</option><option value="genre">Genres</option>
          </select></label>
          <label>At least <input aria-label={`Target ${index + 1} minimum`} type="number" min="1" max="500" step="1" value={rule.min} style={{ width: 65 }} onChange={e => update(index, { min: Math.max(1, Math.min(500, parseInt(e.target.value, 10) || 1)) })} /></label>
          <button type="button" className="nx-ap-btn small" aria-label={`Remove target ${index + 1}`} onClick={() => onChange(value.filter((_, i) => i !== index))}>Remove</button>
        </div>
        <div style={{ display: 'flex', gap: '8px 12px', flexWrap: 'wrap', maxHeight: 150, overflowY: 'auto', marginTop: 10 }}>
          {choices.map(choice => <label key={choice} style={{ display: 'flex', gap: 5, alignItems: 'center', fontSize: 12 }}>
            <input type="checkbox" checked={rule.values.includes(choice)} onChange={e => update(index, { values: e.target.checked ? [...rule.values, choice] : rule.values.filter(v => v !== choice) })} />{choice}
          </label>)}
        </div>
        {!rule.values.length && <p role="status" style={{ fontSize: 12 }}>Choose at least one {rule.kind === 'rating' ? 'rating' : 'genre'} before saving.{!choices.length && ' Connect Radarr and load your library to see genres.'}</p>}
        <small>Any selected value matches this target.</small>
      </fieldset>;
    })}
    <button type="button" className="nx-ap-btn" disabled={disabled || value.length >= 12} onClick={() => onChange([...value, { kind: 'rating', values: ['G', 'PG'], min: 2 }])}>Add minimum target</button>
    <p className="nx-ap-library-muted">Targets are best effort. Missing trailers, unavailable ratings, storage limits, and protected downloads can leave a shortfall. Repairs can replace newer downloads; normal weekly rotation preserves targets already met. Remove all targets to use the original rotation behavior.</p>
    <TrailerQuotaReport entries={report} title="Current pool for these choices" />
  </section>;
}
