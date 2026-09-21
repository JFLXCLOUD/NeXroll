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
 * SequenceConditionPanel - IF/THEN settings in the Sequence Builder's
 * Block settings column. Shown only in Advanced mode.
 *
 * The same editing as BlockConditionEditor (the schedule form's block
 * editor), laid out for the narrow inspector with the builder's own
 * nx-draft controls. Reports every change as { condition, otherwise }.
 */
const SequenceConditionPanel = ({ condition, otherwise, onChange, categories = [] }) => {
  const rules = (condition && Array.isArray(condition.rules)) ? condition.rules : [];
  const getCategoryName = id => categories.find(c => String(c.id) === String(id))?.name || 'a category';
  const setRules = next => onChange(withRules(condition, otherwise, next));
  const updateRule = (i, patch) => setRules(rules.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const setOtherwise = next => onChange({ condition, otherwise: next });

  return (
    <div className="nx-draft-condition">
      <div className="nx-draft-condition-head"><GitBranch size={12} /> Conditions</div>
      <p className="nx-draft-field-hint">When this block plays, and what plays in its place when it doesn't.</p>

      {rules.length === 0 ? (
        <button type="button" className="nx-draft-btn small" onClick={() => onChange({ condition: defaultCondition(), otherwise: otherwise || null })}>
          <Plus size={12} /> Add a condition
        </button>
      ) : <>
        {rules.length > 1 && (
          <label className="nx-draft-field"><span>Play this block</span>
            <select value={condition.match === 'any' ? 'any' : 'all'} onChange={event => onChange({ condition: { ...condition, match: event.target.value }, otherwise })}>
              <option value="all">Only when all rules hold</option>
              <option value="any">When any rule holds</option>
            </select>
          </label>
        )}

        {rules.map((rule, i) => (
          <div className="nx-draft-condition-rule" key={i}>
            <div className="nx-draft-condition-pair">
              <label className="nx-draft-field"><span>{i === 0 ? 'Play' : 'And'}</span>
                <select aria-label={`Rule ${i + 1} when or unless`} value={rule.negate ? 'unless' : 'when'} onChange={event => updateRule(i, { negate: event.target.value === 'unless' })}>
                  <option value="when">when</option>
                  <option value="unless">unless</option>
                </select>
              </label>
              <label className="nx-draft-field"><span>Rule</span>
                <select aria-label={`Rule ${i + 1}`} value={rule.kind} onChange={event => setRules(rules.map((r, j) => (j === i ? { ...defaultRule(event.target.value), negate: r.negate } : r)))}>
                  {RULE_KINDS.map(k => <option key={k.value} value={k.value}>{k.short}</option>)}
                </select>
              </label>
            </div>

            {rule.kind === 'trailers_available' && (
              <div className="nx-draft-condition-pair">
                <label className="nx-draft-field"><span>At least</span>
                  <input type="number" min="1" max="50" value={rule.min ?? 1} onChange={event => updateRule(i, { min: Math.max(1, Number(event.target.value) || 1) })} />
                </label>
                <label className="nx-draft-field"><span>Trailers from</span>
                  <select value={rule.source || 'both'} onChange={event => updateRule(i, { source: event.target.value })}>
                    <option value="both">Movies &amp; TV</option>
                    <option value="movies">Movies only</option>
                    <option value="tv">TV only</option>
                  </select>
                </label>
              </div>
            )}

            {rule.kind === 'genre' && <>
              <div className="nx-draft-field"><span>{rule.negate ? 'Not any of these genres' : 'Any of these genres'}</span>
                <GenrePicker values={rule.values || []} onChange={values => updateRule(i, { values })} />
              </div>
              <p className="nx-server-note"><strong>Jellyfin &amp; Emby only.</strong> They tell NeXroll which movie is about to play. Plex uses one preroll list for every movie, so on Plex this rule is never met and the Otherwise plays.</p>
            </>}

            {rule.kind === 'media_type' && <>
              <label className="nx-draft-field"><span>What is playing</span>
                <select value={rule.value || 'movie'} onChange={event => updateRule(i, { value: event.target.value })}>
                  <option value="movie">A movie</option>
                  <option value="episode">A TV episode</option>
                </select>
              </label>
              <p className="nx-server-note"><strong>Jellyfin &amp; Emby</strong> say whether a movie or an episode is starting. Plex only runs prerolls before movies, so on Plex it is always a movie.</p>
            </>}

            {rule.kind === 'time_window' && <>
              <div className="nx-draft-condition-pair even">
                <label className="nx-draft-field"><span>From</span>
                  <input type="time" value={rule.start || ''} onChange={event => updateRule(i, { start: event.target.value })} />
                </label>
                <label className="nx-draft-field"><span>To</span>
                  <input type="time" value={rule.end || ''} onChange={event => updateRule(i, { end: event.target.value })} />
                </label>
              </div>
              <div className="nx-draft-weekday nx-draft-condition-days">
                {WEEKDAYS.map(day => {
                  const on = (rule.days || []).includes(day.value);
                  return (
                    <button type="button" key={day.value} className={on ? 'on' : ''} aria-pressed={on} title={day.value}
                      onClick={() => updateRule(i, { days: on ? rule.days.filter(d => d !== day.value) : [...(rule.days || []), day.value] })}>
                      {day.short.slice(0, 2)}
                    </button>
                  );
                })}
              </div>
              <p className="nx-draft-field-hint">No days means every day. A window past midnight, like 22:00 to 03:00, belongs to the day it starts.</p>
            </>}

            <button type="button" className="nx-draft-btn small ghost" onClick={() => setRules(rules.filter((_, j) => j !== i))}>
              <Trash2 size={11} /> Remove rule
            </button>
          </div>
        ))}

        <button type="button" className="nx-draft-btn small" onClick={() => setRules([...rules, defaultRule()])}>
          <Plus size={12} /> Add another rule
        </button>

        <label className="nx-draft-field nx-draft-condition-otherwise"><span>Otherwise</span>
          <select value={otherwiseChoiceOf(otherwise)} onChange={event => setOtherwise(otherwiseForChoice(event.target.value, categories))}>
            {OTHERWISE_CHOICES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
          </select>
        </label>
        {otherwiseChoiceOf(otherwise) === 'random' && (
          <div className="nx-draft-condition-pair">
            <label className="nx-draft-field"><span>Category</span>
              <select value={otherwise.category_id || ''} onChange={event => setOtherwise({ ...otherwise, category_id: Number(event.target.value) })}>
                {categories.map(category => <option key={category.id} value={category.id}>{category.name}</option>)}
              </select>
            </label>
            <label className="nx-draft-field"><span>How many</span>
              <input type="number" min="1" max="10" value={otherwise.count || 1} onChange={event => setOtherwise({ ...otherwise, count: Math.max(1, Math.min(10, Number(event.target.value) || 1)) })} />
            </label>
          </div>
        )}
        {otherwiseChoiceOf(otherwise) === 'library_trailers' && (
          <label className="nx-draft-field"><span>How many</span>
            <input type="number" min="1" max="10" value={otherwise.count || 1} onChange={event => setOtherwise({ ...otherwise, count: Math.max(1, Math.min(10, Number(event.target.value) || 1)) })} />
          </label>
        )}
        {otherwiseChoiceOf(otherwise) === 'nexup_trailers' && (
          <div className="nx-draft-condition-pair">
            <label className="nx-draft-field"><span>Trailers from</span>
              <select value={otherwise.source || 'both'} onChange={event => setOtherwise({ ...otherwise, source: event.target.value })}>
                <option value="both">Movies &amp; TV</option>
                <option value="movies">Movies only</option>
                <option value="tv">TV only</option>
              </select>
            </label>
            <label className="nx-draft-field"><span>How many</span>
              <input type="number" min="1" max="10" value={otherwise.count || 1} onChange={event => setOtherwise({ ...otherwise, count: Math.max(1, Math.min(10, Number(event.target.value) || 1)) })} />
            </label>
          </div>
        )}

        <p className="nx-draft-condition-summary">{describeBlockCondition(condition, otherwise, getCategoryName)}</p>
        <button type="button" className="nx-draft-btn small ghost" onClick={() => onChange({ condition: null, otherwise: null })}>
          <Trash2 size={11} /> Remove all conditions
        </button>
      </>}
    </div>
  );
};

export default SequenceConditionPanel;
