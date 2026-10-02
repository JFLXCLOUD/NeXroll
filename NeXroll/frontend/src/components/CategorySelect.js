import React, { useState } from 'react';
import { Plus } from 'lucide-react';

const NEW_CATEGORY = '__new_category__';

/**
 * CategorySelect - a single-category dropdown that can create the category on
 * the spot. Picking "+ New category…" turns the dropdown into a name field
 * with Create and Cancel; the new category is then selected. Typing the name
 * of an existing category selects it instead of making a duplicate.
 *
 * Used where prerolls are put into a category (community downloads, folder
 * import, the Library's bulk action), so nobody has to leave the page to make
 * one first. `onChange` receives the selected id as a string, as a native
 * select would; `onCreateCategory(name)` returns the created category or null.
 */
const CategorySelect = ({
  categories = [],
  value,
  onChange,
  onCreateCategory,
  emptyLabel = 'No category',
  className,
  style,
  title,
  disabled = false,
  ariaLabel,
}) => {
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const sorted = [...categories].sort((a, b) => String(a.name).localeCompare(String(b.name)));

  const cancel = () => {
    setCreating(false);
    setName('');
  };

  const submit = async () => {
    const wanted = name.trim();
    if (!wanted || busy) return;
    const existing = categories.find(c => String(c.name).trim().toLowerCase() === wanted.toLowerCase());
    if (existing) {
      onChange(String(existing.id));
      cancel();
      return;
    }
    setBusy(true);
    try {
      const created = await onCreateCategory(wanted);
      if (created && created.id != null) {
        onChange(String(created.id));
        cancel();
      }
    } finally {
      setBusy(false);
    }
  };

  if (creating) {
    return (
      <span className="nx-category-create">
        <input
          type="text"
          className={className}
          value={name}
          placeholder="New category name"
          aria-label="New category name"
          autoFocus
          disabled={busy}
          onChange={event => setName(event.target.value)}
          onClick={event => event.stopPropagation()}
          onKeyDown={event => {
            if (event.key === 'Enter') { event.preventDefault(); submit(); }
            if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); cancel(); }
          }}
        />
        <button type="button" className="button" disabled={!name.trim() || busy} onClick={event => { event.stopPropagation(); submit(); }}>
          <Plus size={13} /> {busy ? 'Creating…' : 'Create'}
        </button>
        <button type="button" className="button button-secondary" disabled={busy} onClick={event => { event.stopPropagation(); cancel(); }}>
          Cancel
        </button>
      </span>
    );
  }

  return (
    <select
      className={className}
      style={style}
      title={title}
      aria-label={ariaLabel}
      disabled={disabled}
      value={value == null ? '' : String(value)}
      onChange={event => {
        if (event.target.value === NEW_CATEGORY) {
          setCreating(true);
          return;
        }
        onChange(event.target.value);
      }}
    >
      {emptyLabel !== null && <option value="">{emptyLabel}</option>}
      {sorted.map(category => <option key={category.id} value={String(category.id)}>{category.name}</option>)}
      {onCreateCategory && <option value={NEW_CATEGORY}>+ New category…</option>}
    </select>
  );
};

export default CategorySelect;
