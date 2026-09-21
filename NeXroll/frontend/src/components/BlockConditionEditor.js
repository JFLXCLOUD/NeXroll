import React from 'react';
import { GitBranch, Plus, Trash2 } from 'lucide-react';
import {
  RULE_KINDS,
  WEEKDAYS,
  OTHERWISE_CHOICES,
  defaultRule,
  defaultCondition,
  describeBlockCondition,
  otherwiseChoiceOf,
  otherwiseForChoice,
  withRules,
} from '../utils/sequenceConditions';
import GenrePicker from './GenrePicker';

/**
 * BlockConditionEditor - the IF/THEN section of the block editor.
 *
 * Only shown in the Sequence Builder's Advanced mode. Edits a block's
 * `condition` (when it plays) and `otherwise` (what plays in its place when
 * it doesn't). Controlled: every change is reported through onChange as
 * { condition, otherwise }, with condition null meaning "always plays".
 */

const inputStyle = {
  padding: '7px 10px',
  border: '2px solid var(--border-color)',
  borderRadius: '6px',
  background: 'var(--input-bg)',
  color: 'var(--text-color)',
  fontSize: '13px',
  boxSizing: 'border-box',
};

const labelStyle = {
  display: 'block',
  marginBottom: '6px',
  color: 'var(--text-color)',
  fontWeight: 600,
  fontSize: '13px',
};

const hintStyle = {
  display: 'block',
  marginTop: '6px',
  color: 'var(--text-secondary)',
  fontSize: '11px',
  lineHeight: 1.4,
};

const smallButton = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  padding: '7px 12px',
  border: '1px solid var(--border-color)',
  borderRadius: '6px',
  background: 'var(--card-bg)',
  color: 'var(--text-color)',
  cursor: 'pointer',
  fontSize: '12px',
  fontWeight: 600,
};

const RuleRow = ({ rule, index, onChange, onRemove, canRemove }) => {
  const set = (patch) => onChange(index, { ...rule, ...patch });
  const toggleDay = (day) => {
    const days = Array.isArray(rule.days) ? rule.days : [];
    set({ days: days.includes(day) ? days.filter(d => d !== day) : [...days, day] });
  };

  return (
    <div style={{
      padding: '10px',
      border: '1px solid var(--border-color)',
      borderRadius: '8px',
      background: 'var(--card-bg)',
    }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
        <select
          aria-label="When or unless"
          value={rule.negate ? 'unless' : 'when'}
          onChange={(e) => set({ negate: e.target.value === 'unless' })}
          style={inputStyle}
        >
          <option value="when">when</option>
          <option value="unless">unless</option>
        </select>
        <select
          aria-label="Rule"
          value={rule.kind}
          onChange={(e) => onChange(index, { ...defaultRule(e.target.value), negate: rule.negate })}
          style={inputStyle}
        >
          {RULE_KINDS.map(k => <option key={k.value} value={k.value}>{k.label}</option>)}
        </select>

        {rule.kind === 'trailers_available' && (
          <>
            <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>at least</span>
            <input
              type="number"
              min="1"
              max="50"
              aria-label="Minimum trailers"
              value={rule.min ?? 1}
              onChange={(e) => set({ min: Math.max(parseInt(e.target.value, 10) || 1, 1) })}
              style={{ ...inputStyle, width: '70px' }}
            />
            <select
              aria-label="Trailer source"
              value={rule.source || 'both'}
              onChange={(e) => set({ source: e.target.value })}
              style={inputStyle}
            >
              <option value="both">movie or TV</option>
              <option value="movies">movie</option>
              <option value="tv">TV</option>
            </select>
          </>
        )}

        {rule.kind === 'media_type' && (
          <select
            aria-label="Media type"
            value={rule.value || 'movie'}
            onChange={(e) => set({ value: e.target.value })}
            style={inputStyle}
          >
            <option value="movie">is a movie</option>
            <option value="episode">is a TV episode</option>
          </select>
        )}

        {rule.kind === 'time_window' && (
          <>
            <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>from</span>
            <input
              type="time"
              aria-label="Start time"
              value={rule.start || ''}
              onChange={(e) => set({ start: e.target.value })}
              style={inputStyle}
            />
            <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>to</span>
            <input
              type="time"
              aria-label="End time"
              value={rule.end || ''}
              onChange={(e) => set({ end: e.target.value })}
              style={inputStyle}
            />
          </>
        )}

        {canRemove && (
          <button
            type="button"
            onClick={() => onRemove(index)}
            aria-label="Remove rule"
            title="Remove rule"
            style={{ ...smallButton, marginLeft: 'auto', padding: '7px 9px' }}
          >
            <Trash2 size={14} />
          </button>
        )}
      </div>

      {rule.kind === 'time_window' && (
        <div style={{ marginTop: '8px' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {WEEKDAYS.map(d => {
              const on = Array.isArray(rule.days) && rule.days.includes(d.value);
              return (
                <button
                  key={d.value}
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggleDay(d.value)}
                  style={{
                    ...smallButton,
                    padding: '5px 10px',
                    background: on ? 'var(--accent-color)' : 'var(--card-bg)',
                    color: on ? 'white' : 'var(--text-color)',
                    borderColor: on ? 'var(--accent-color)' : 'var(--border-color)',
                  }}
                >
                  {d.short}
                </button>
              );
            })}
          </div>
          <small style={hintStyle}>
            No days selected means every day. A window that ends after midnight, such as 22:00 to 03:00,
            belongs to the day it starts on.
          </small>
        </div>
      )}

      {rule.kind === 'genre' && (
        <div style={{ marginTop: '8px' }}>
          <GenrePicker values={rule.values || []} onChange={values => set({ values })} />
          <small style={hintStyle}>
            <strong>Jellyfin &amp; Emby only.</strong> They tell NeXroll which movie is about to play. Plex uses one
            preroll list for every movie, so on Plex this rule is never met and the Otherwise plays.
          </small>
        </div>
      )}

      {rule.kind === 'media_type' && (
        <small style={hintStyle}>
          Jellyfin and Emby tell NeXroll what is about to play. Plex only runs prerolls before movies,
          so on Plex this is always a movie.
        </small>
      )}
    </div>
  );
};

const BlockConditionEditor = ({ condition, otherwise, onChange, categories = [] }) => {
  const rules = (condition && Array.isArray(condition.rules)) ? condition.rules : [];
  const sortedCategories = [...categories].sort((a, b) => a.name.localeCompare(b.name));
  const getCategoryName = (id) => (categories.find(c => c.id === id) || {}).name || 'a category';

  const emit = (nextCondition, nextOtherwise) => onChange({ condition: nextCondition, otherwise: nextOtherwise });
  const setRules = (nextRules) => onChange(withRules(condition, otherwise, nextRules));
  const updateRule = (i, rule) => setRules(rules.map((r, j) => (j === i ? rule : r)));
  const removeRule = (i) => setRules(rules.filter((_, j) => j !== i));

  const otherwiseChoice = otherwiseChoiceOf(otherwise);
  const setOtherwiseChoice = (choice) => emit(condition, otherwiseForChoice(choice, categories));
  const patchOtherwise = (patch) => emit(condition, { ...otherwise, ...patch });

  return (
    <div style={{
      marginTop: '20px',
      padding: '16px',
      border: '2px solid var(--border-color)',
      borderRadius: '10px',
      background: 'var(--hover-bg)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
        <GitBranch size={16} />
        <span style={{ fontWeight: 700, fontSize: '14px', color: 'var(--text-color)' }}>Conditions</span>
      </div>
      <small style={{ ...hintStyle, marginTop: 0, marginBottom: '12px' }}>
        Decide when this block plays, and what plays in its place when it doesn't.
      </small>

      {rules.length === 0 ? (
        <button type="button" style={smallButton} onClick={() => emit(defaultCondition(), otherwise || null)}>
          <Plus size={14} /> Add a condition
        </button>
      ) : (
        <>
          <label style={labelStyle}>Play this block</label>
          {rules.length > 1 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', flexWrap: 'wrap' }}>
              <select
                aria-label="Match all or any"
                value={condition.match === 'any' ? 'any' : 'all'}
                onChange={(e) => emit({ ...condition, match: e.target.value }, otherwise)}
                style={inputStyle}
              >
                <option value="all">only when all of these hold</option>
                <option value="any">when any of these holds</option>
              </select>
            </div>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {rules.map((rule, i) => (
              <RuleRow
                key={i}
                rule={rule}
                index={i}
                onChange={updateRule}
                onRemove={removeRule}
                canRemove
              />
            ))}
          </div>
          <button
            type="button"
            style={{ ...smallButton, marginTop: '8px' }}
            onClick={() => setRules([...rules, defaultRule()])}
          >
            <Plus size={14} /> Add another rule
          </button>

          <div style={{ marginTop: '16px' }}>
            <label style={labelStyle} htmlFor="otherwise-choice">Otherwise</label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
              <select
                id="otherwise-choice"
                value={otherwiseChoice}
                onChange={(e) => setOtherwiseChoice(e.target.value)}
                style={inputStyle}
              >
                {OTHERWISE_CHOICES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>

              {otherwiseChoice === 'random' && (
                <>
                  <select
                    aria-label="Alternative category"
                    value={otherwise.category_id || ''}
                    onChange={(e) => patchOtherwise({ category_id: parseInt(e.target.value, 10) })}
                    style={inputStyle}
                  >
                    {sortedCategories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                  <input
                    type="number"
                    min="1"
                    max="20"
                    aria-label="Alternative count"
                    value={otherwise.count || 1}
                    onChange={(e) => patchOtherwise({ count: Math.max(parseInt(e.target.value, 10) || 1, 1) })}
                    style={{ ...inputStyle, width: '70px' }}
                  />
                </>
              )}

              {otherwiseChoice === 'library_trailers' && (
                <input
                  type="number"
                  min="1"
                  max="10"
                  aria-label="Alternative library trailer count"
                  value={otherwise.count || 1}
                  onChange={(e) => patchOtherwise({ count: Math.max(parseInt(e.target.value, 10) || 1, 1) })}
                  style={{ ...inputStyle, width: '70px' }}
                />
              )}

              {otherwiseChoice === 'nexup_trailers' && (
                <>
                  <select
                    aria-label="Alternative trailer source"
                    value={otherwise.source || 'both'}
                    onChange={(e) => patchOtherwise({ source: e.target.value })}
                    style={inputStyle}
                  >
                    <option value="both">Movies and TV</option>
                    <option value="movies">Movies</option>
                    <option value="tv">TV</option>
                  </select>
                  <input
                    type="number"
                    min="1"
                    max="10"
                    aria-label="Alternative trailer count"
                    value={otherwise.count || 1}
                    onChange={(e) => patchOtherwise({ count: Math.max(parseInt(e.target.value, 10) || 1, 1) })}
                    style={{ ...inputStyle, width: '70px' }}
                  />
                </>
              )}
            </div>
          </div>

          <div style={{
            marginTop: '14px',
            padding: '10px 12px',
            borderRadius: '6px',
            background: 'var(--card-bg)',
            border: '1px dashed var(--border-color)',
            fontSize: '12px',
            color: 'var(--text-color)',
            lineHeight: 1.5,
          }}>
            {describeBlockCondition(condition, otherwise, getCategoryName)}
          </div>

          <button
            type="button"
            style={{ ...smallButton, marginTop: '10px', color: 'var(--text-secondary)' }}
            onClick={() => emit(null, null)}
          >
            <Trash2 size={14} /> Remove all conditions
          </button>
        </>
      )}
    </div>
  );
};

export default BlockConditionEditor;
