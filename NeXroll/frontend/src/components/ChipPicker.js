import React, { useId, useState } from 'react';
import { Plus, X } from 'lucide-react';

/**
 * ChipPicker - a list of short values shown as removable chips, with a text
 * box (and optional suggestions) to add more. Used by the genre, tag and file
 * path rules. Duplicates are ignored case-insensitively, as the rules match.
 */
const ChipPicker = ({ values = [], onChange, suggestions = [], placeholder, morePlaceholder, label, hint }) => {
  const [draft, setDraft] = useState('');
  const listId = useId();
  const open = suggestions.filter(s => !values.some(v => v.toLowerCase() === s.toLowerCase()));

  const add = (name) => {
    const clean = String(name || '').trim();
    if (!clean || values.some(v => v.toLowerCase() === clean.toLowerCase())) { setDraft(''); return; }
    onChange([...values, clean]);
    setDraft('');
  };

  return (
    <div className="nx-genre-picker">
      {values.length > 0 && (
        <div className="nx-genre-chips">
          {values.map(value => (
            <span key={value} className="nx-genre-chip">
              {value}
              <button type="button" aria-label={`Remove ${value}`} onClick={() => onChange(values.filter(v => v !== value))}><X size={11} /></button>
            </span>
          ))}
        </div>
      )}
      <div className="nx-genre-add">
        <input
          list={open.length ? listId : undefined}
          value={draft}
          placeholder={values.length ? (morePlaceholder || placeholder) : placeholder}
          aria-label={label}
          onChange={event => setDraft(event.target.value)}
          onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); add(draft); } }}
        />
        {open.length > 0 && <datalist id={listId}>{open.map(s => <option key={s} value={s} />)}</datalist>}
        <button type="button" className="nx-draft-btn small" onClick={() => add(draft)} disabled={!draft.trim()}><Plus size={11} /> Add</button>
      </div>
      {hint && <small className="nx-genre-hint">{hint}</small>}
    </div>
  );
};

export default ChipPicker;
