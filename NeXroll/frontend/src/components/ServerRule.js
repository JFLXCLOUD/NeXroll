import React from 'react';
import { SERVER_CHOICES } from '../utils/sequenceConditions';

/**
 * The "Media server" condition: which servers this block plays on. Used by
 * both the Sequence Builder's inspector and the schedule form's block editor.
 */
export default function ServerRule({ rule, onChange }) {
  const values = Array.isArray(rule.values) ? rule.values : [];
  const toggle = (value, on) => onChange({ values: on ? [...values, value] : values.filter(v => v !== value) });
  return <fieldset style={{ minWidth: 0, border: '1px solid var(--border-color)', borderRadius: 8, padding: 10, margin: '10px 0' }}>
    <legend>{rule.negate ? 'Not on these servers' : 'On these servers'}</legend>
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 14px' }}>
      {SERVER_CHOICES.map(({ value, label }) => <label key={value} style={{ display: 'flex', gap: 5, alignItems: 'center', fontSize: 12 }}>
        <input type="checkbox" checked={values.includes(value)} onChange={e => toggle(value, e.target.checked)} />{label}
      </label>)}
    </div>
    <p className="nx-draft-field-hint">
      Play different prerolls on each server: put this server's prerolls in their own category, and choose another
      category under Otherwise for the rest. A Jellyfin or Emby plugin too old to say which server it is counts as
      not matching, so it gets the Otherwise.
    </p>
    {!values.length && <p role="status" className="nx-draft-field-hint">Choose at least one server before saving.</p>}
  </fieldset>;
}
