import React, { useId, useState } from 'react';
import { Plus, X } from 'lucide-react';
import { useLibraryGenres } from '../utils/sequenceConditions';

// Offered when no Jellyfin/Emby library can be asked; typed names still work.
const COMMON_GENRES = ['Action', 'Animation', 'Comedy', 'Documentary', 'Drama', 'Family', 'Fantasy', 'Horror', 'Romance', 'Science Fiction', 'Thriller'];

/**
 * GenrePicker - chooses the genres a genre rule matches. Suggestions come from
 * the connected Jellyfin/Emby libraries, so they match the names those servers
 * actually use; any name can still be typed. Matching is case-insensitive.
 */
const GenrePicker = ({ values = [], onChange }) => {
  const library = useLibraryGenres();
  const [draft, setDraft] = useState('');
  const listId = useId();
  const suggestions = (library.length ? library : COMMON_GENRES)
    .filter(g => !values.some(v => v.toLowerCase() === g.toLowerCase()));

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
          list={listId}
          value={draft}
          placeholder={values.length ? 'Add another genre' : 'e.g. Horror'}
          aria-label="Genre"
          onChange={event => setDraft(event.target.value)}
          onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); add(draft); } }}
        />
        <datalist id={listId}>{suggestions.map(g => <option key={g} value={g} />)}</datalist>
        <button type="button" className="nx-draft-btn small" onClick={() => add(draft)} disabled={!draft.trim()}><Plus size={11} /> Add</button>
      </div>
      {library.length === 0 && (
        <small className="nx-genre-hint">Connect Jellyfin or Emby to pick from your library's own genre names.</small>
      )}
    </div>
  );
};

export default GenrePicker;
