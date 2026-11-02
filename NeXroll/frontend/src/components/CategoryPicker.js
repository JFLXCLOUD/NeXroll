import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Check, ChevronDown, Plus, X } from 'lucide-react';

/**
 * CategoryPicker - choose several categories for a preroll (upload details,
 * edit dialog), and create one on the spot.
 *
 * Categories are flat tags in the UI. For storage the component still takes
 * `primaryId` + `secondaryIds` and reports `onChange(primary, secondary)`: the
 * first category chosen is the legacy primary, which only picks the upload
 * folder (see utils/prerollCategories.js).
 *
 * The field's text box is the search box. Arrow keys move through the list,
 * Enter ticks the highlighted category (or creates the typed name when nothing
 * matches), Backspace on an empty box removes the last chip and Escape closes.
 * Your categories are listed alphabetically before the system ones.
 */
const CategoryPicker = ({
  categories,
  primaryId,
  secondaryIds,
  onChange,
  onCreateCategory,
  label = 'Categories',
  placeholder = 'Choose categories',
  disabled = false,
}) => {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  // "New category" switches the search box to asking for the new name.
  const [naming, setNaming] = useState(false);
  const [creating, setCreating] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [openUp, setOpenUp] = useState(false);
  const containerRef = useRef(null);
  const fieldRef = useRef(null);
  const inputRef = useRef(null);
  const listRef = useRef(null);
  const baseId = useMemo(() => 'nx-catpicker-' + Math.random().toString(36).slice(2), []);
  const listboxId = `${baseId}-list`;

  useEffect(() => {
    const onDocClick = (event) => {
      if (containerRef.current && !containerRef.current.contains(event.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, []);

  useEffect(() => {
    if (!open) {
      setNaming(false);
      setActiveIndex(-1);
      return;
    }
    // Open upward when the list would run off the bottom of the window.
    const field = fieldRef.current;
    if (field && typeof window !== 'undefined') {
      const rect = field.getBoundingClientRect();
      const below = window.innerHeight - rect.bottom;
      setOpenUp(below < 300 && rect.top > below);
    }
  }, [open]);

  const items = useMemo(() => {
    const list = Array.isArray(categories)
      ? categories.map(c => ({ id: String(c.id), name: String(c.name ?? ''), system: !!c.is_system }))
      : [];
    const byName = (a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });
    return [...list.filter(i => !i.system).sort(byName), ...list.filter(i => i.system).sort(byName)];
  }, [categories]);

  // Chosen ids in the order they were chosen, so the first one stays first.
  // Ids missing from `categories` are kept so a change here can't drop them.
  const selectedIds = [primaryId ? String(primaryId) : '', ...(Array.isArray(secondaryIds) ? secondaryIds.map(String) : [])]
    .filter((value, index, all) => value && all.indexOf(value) === index);
  const selectedSet = new Set(selectedIds);
  const selectedItems = selectedIds.map(value => items.find(i => i.id === value)).filter(Boolean);

  const trimmedQuery = query.trim();
  const filtered = items.filter(i => i.name.toLowerCase().includes(trimmedQuery.toLowerCase()));
  const existsByName = items.some(i => i.name.toLowerCase() === trimmedQuery.toLowerCase());
  const showCreate = !!onCreateCategory && trimmedQuery.length > 0 && !existsByName;
  // Keyboard order follows the screen: the Create row sits above the list.
  const options = [...(showCreate ? [{ create: true }] : []), ...filtered];
  const firstSystem = filtered.findIndex(i => i.system);

  // Typing highlights the first match, or Create when nothing matches (and
  // always after "New category", where the typed text is the new name).
  useEffect(() => {
    if (!open) return;
    if (!trimmedQuery) { setActiveIndex(-1); return; }
    setActiveIndex(showCreate && filtered.length > 0 && !naming ? 1 : 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trimmedQuery, open, naming]);

  useEffect(() => {
    if (activeIndex < 0 || !listRef.current) return;
    const el = listRef.current.querySelector(`[data-index="${activeIndex}"]`);
    if (el && el.scrollIntoView) el.scrollIntoView({ block: 'nearest' });
  }, [activeIndex]);

  const emit = (ids) => {
    const unique = ids.filter((value, index, all) => value && all.indexOf(value) === index);
    onChange(unique[0] || '', unique.slice(1));
  };

  const toggle = (id) => {
    id = String(id);
    if (selectedSet.has(id)) emit(selectedIds.filter(x => x !== id));
    else emit([...selectedIds, id]);
  };

  const handleCreateCategory = async () => {
    if (!showCreate || creating) return;
    try {
      setCreating(true);
      const created = await onCreateCategory(trimmedQuery);
      if (created && created.id) {
        emit([...selectedIds, String(created.id)]);
        setQuery('');
        setNaming(false);
      }
    } catch (err) {
      alert('Failed to create category: ' + (err && err.message ? err.message : err));
    } finally {
      setCreating(false);
    }
  };

  const choose = (option) => {
    if (!option) return;
    if (option.create) handleCreateCategory();
    else toggle(option.id);
  };

  const openPicker = () => {
    if (disabled) return;
    setOpen(true);
    if (inputRef.current) inputRef.current.focus();
  };

  const onKeyDown = (event) => {
    if (disabled) return;
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (!open) { setOpen(true); return; }
      if (options.length === 0) return;
      const step = event.key === 'ArrowDown' ? 1 : -1;
      setActiveIndex(prev => (prev < 0 ? (step > 0 ? 0 : options.length - 1) : (prev + step + options.length) % options.length));
    } else if (event.key === 'Enter') {
      event.preventDefault();
      if (!open) { setOpen(true); return; }
      const option = options[activeIndex];
      if (option) {
        choose(option);
        if (!option.create) setQuery('');
      }
    } else if (event.key === 'Escape') {
      if (open) {
        event.preventDefault();
        event.stopPropagation();
        setOpen(false);
      }
    } else if (event.key === 'Backspace' && !query && selectedItems.length > 0) {
      toggle(selectedItems[selectedItems.length - 1].id);
    } else if (event.key === 'Tab') {
      setOpen(false);
    }
  };

  const optionId = (index) => `${baseId}-opt-${index}`;
  const inputPlaceholder = naming
    ? 'Name the new category, then press Enter'
    : (selectedItems.length ? 'Add another…' : placeholder);

  return (
    <div ref={containerRef} className={`nx-catpicker${disabled ? ' is-disabled' : ''}`}>
      {label && <label className="nx-label" htmlFor={`${baseId}-input`}>{label}</label>}

      <div className="nx-catpicker-anchor">
      <div
        ref={fieldRef}
        className={`nx-catpicker-input${open ? ' open' : ''}`}
        onClick={openPicker}
      >
        {selectedItems.map(i => (
          <span key={i.id} className="nx-chip">
            {i.name}
            {!disabled && (
              <button
                type="button"
                className="nx-chip-x"
                onClick={(event) => { event.stopPropagation(); toggle(i.id); }}
                aria-label={`Remove ${i.name}`}
                title="Remove"
              >
                <X size={12} />
              </button>
            )}
          </span>
        ))}

        <input
          id={`${baseId}-input`}
          ref={inputRef}
          type="text"
          className="nx-catpicker-search"
          role="combobox"
          aria-expanded={open}
          aria-controls={listboxId}
          aria-autocomplete="list"
          aria-activedescendant={open && activeIndex >= 0 ? optionId(activeIndex) : undefined}
          aria-label={label ? undefined : 'Categories'}
          placeholder={inputPlaceholder}
          value={query}
          disabled={disabled}
          autoComplete="off"
          onChange={(event) => { setQuery(event.target.value); if (!open) setOpen(true); }}
          onFocus={() => { if (!disabled) setOpen(true); }}
          onKeyDown={onKeyDown}
        />

        <span className="nx-catpicker-tools">
          {selectedItems.length > 0 && !disabled && (
            <button
              type="button"
              className="nx-catpicker-clear"
              onClick={(event) => { event.stopPropagation(); emit([]); setQuery(''); }}
              title="Remove every category"
            >
              Clear
            </button>
          )}
          <button
            type="button"
            className="nx-catpicker-toggle"
            tabIndex={-1}
            disabled={disabled}
            aria-label={open ? 'Close category list' : 'Open category list'}
            onClick={(event) => { event.stopPropagation(); if (open) setOpen(false); else openPicker(); }}
          >
            <ChevronDown size={16} />
          </button>
        </span>
      </div>

      {open && (
        <div className={`nx-catpicker-dropdown${openUp ? ' is-up' : ''}`}>
          {onCreateCategory && !trimmedQuery && (
            <div className="nx-catpicker-create">
              <button
                type="button"
                className="nx-catpicker-create-btn"
                onClick={(event) => { event.stopPropagation(); setNaming(true); if (inputRef.current) inputRef.current.focus(); }}
              >
                <Plus size={14} /> New category
              </button>
            </div>
          )}
          {showCreate && (
            <div className="nx-catpicker-create">
              <button
                type="button"
                id={optionId(0)}
                className={`nx-catpicker-create-btn is-named${activeIndex === 0 ? ' is-active' : ''}`}
                onMouseDown={(event) => event.preventDefault()}
                onClick={(event) => { event.stopPropagation(); handleCreateCategory(); }}
                onMouseEnter={() => setActiveIndex(0)}
                disabled={creating}
              >
                <Plus size={14} /> {creating ? 'Creating…' : <>Create &ldquo;{trimmedQuery}&rdquo;</>}
              </button>
            </div>
          )}
          <div id={listboxId} ref={listRef} className="nx-catpicker-list" role="listbox" aria-multiselectable="true" aria-label={label || 'Categories'}>
            {filtered.length === 0 ? (
              <div className="nx-catpicker-empty">
                {items.length === 0 ? 'No categories yet' : `No category matches "${trimmedQuery}"`}
              </div>
            ) : filtered.map((i, index) => {
              const optionIndex = index + (showCreate ? 1 : 0);
              const selected = selectedSet.has(i.id);
              return (
                <React.Fragment key={i.id}>
                  {index === firstSystem && <div className="nx-catpicker-group" role="presentation">System categories</div>}
                  <div
                    id={optionId(optionIndex)}
                    data-index={optionIndex}
                    className={`nx-catpicker-item${selected ? ' selected' : ''}${activeIndex === optionIndex ? ' is-active' : ''}`}
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => toggle(i.id)}
                    onMouseEnter={() => setActiveIndex(optionIndex)}
                    role="option"
                    aria-selected={selected}
                  >
                    <span className="nx-catpicker-check" aria-hidden="true">{selected && <Check size={12} strokeWidth={3} />}</span>
                    <span className="nx-catpicker-name">{i.name}</span>
                  </div>
                </React.Fragment>
              );
            })}
          </div>
          <div className="nx-catpicker-foot">
            <span>{selectedItems.length ? `${selectedItems.length} selected` : 'None selected'}</span>
            <button type="button" className="nx-catpicker-done" onClick={(event) => { event.stopPropagation(); setOpen(false); }}>
              Done
            </button>
          </div>
        </div>
      )}
      </div>
    </div>
  );
};

export default CategoryPicker;
