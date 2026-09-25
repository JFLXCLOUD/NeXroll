import React from 'react';
import { AUDIO_FORMATS } from '../utils/audioFormats';

export default function AudioFormatRule({ rule, onChange }) {
  const values = Array.isArray(rule.values) ? rule.values : [];
  return <fieldset style={{ minWidth: 0, border: '1px solid var(--border-color)', borderRadius: 8, padding: 10, margin: '10px 0' }}>
    <legend>Stored audio format</legend>
    <label style={{ display: 'block', fontSize: 12 }}>Check
      <select aria-label="Audio track to check" value={rule.track || 'default'} onChange={e => onChange({ track: e.target.value })} style={{ width: '100%', margin: '6px 0 10px' }}>
        <option value="default">Default / only stored audio track</option>
        <option value="any">Any stored audio track</option>
      </select>
    </label>
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 12px' }}>
      {AUDIO_FORMATS.map(([key, label]) => <label key={key} style={{ display: 'flex', gap: 5, alignItems: 'center', fontSize: 12 }}>
        <input type="checkbox" checked={values.includes(key)} onChange={e => onChange({ values: e.target.checked ? [...values, key] : values.filter(v => v !== key) })} />{label}
      </label>)}
    </div>
    <p className="nx-draft-field-hint">Jellyfin &amp; Emby only. Matches file metadata, not the viewer's selected track or transcoded output. Multiple versions or an unclear default make the default unknown. Unknown metadata and Plex use Otherwise, even for an Unless rule.</p>
    <p className="nx-draft-field-hint">Select any formats that should match. DTS includes DTS-HD. These choices do not distinguish Atmos, DTS:X, or THX.</p>
    {!values.length && <p role="status" className="nx-draft-field-hint">Choose at least one audio format before saving.</p>}
  </fieldset>;
}
