import React, { useState } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import BlockConditionEditor from './BlockConditionEditor';
import { describeCondition, describeOtherwise, blocksHaveConditions, needsPlaybackInfo, genresInSequence } from '../utils/sequenceConditions';

const categories = [
  { id: 4, name: 'House Intros' },
  { id: 2, name: 'Bumpers' },
];

// Holds the editor's value the way BlockEditor does and exposes it for asserts.
let latest;
const Harness = ({ initial = { condition: null, otherwise: null } }) => {
  const [value, setValue] = useState(initial);
  latest = value;
  return (
    <BlockConditionEditor
      condition={value.condition}
      otherwise={value.otherwise}
      onChange={setValue}
      categories={categories}
    />
  );
};

test('availability can select a library rating pool or follow a trailer block', () => {
  render(<Harness />);
  fireEvent.click(screen.getByRole('button', { name: /add a condition/i }));
  fireEvent.change(screen.getByLabelText('Trailer pool'), { target: { value: 'library' } });
  fireEvent.click(screen.getByLabelText('Restrict age ratings'));
  fireEvent.click(screen.getByLabelText('PG'));
  expect(latest.condition.rules[0]).toMatchObject({ pool: 'library', ratings: ['PG'], restrict_ratings: true });
  fireEvent.change(screen.getByLabelText('Trailer pool'), { target: { value: 'block' } });
  expect(latest.condition.rules[0].pool).toBe('block');
  expect(screen.queryByLabelText('Restrict age ratings')).not.toBeInTheDocument();
  expect(screen.getByText(/Uses this trailer block/)).toBeInTheDocument();
});

describe('BlockConditionEditor', () => {
  test('adding a condition starts with "a trailer is available" and skips otherwise', () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole('button', { name: /add a condition/i }));
    expect(latest.condition).toEqual({
      match: 'all',
      rules: [{ kind: 'trailers_available', source: 'both', min: 1 }],
    });
    expect(latest.otherwise).toBeNull();
    expect(screen.getByText(/a movie or TV trailer is available/)).toBeInTheDocument();
    expect(screen.getByText(/the block is skipped/)).toBeInTheDocument();
  });

  test('choosing a category alternative defaults to the first category by name', () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole('button', { name: /add a condition/i }));
    fireEvent.change(screen.getByLabelText('Otherwise'), { target: { value: 'random' } });
    expect(latest.otherwise).toEqual({ type: 'random', category_id: 2, count: 1 });
    expect(screen.getByText(/1 preroll from Bumpers play instead/)).toBeInTheDocument();
  });

  test('"unless" negates a rule', () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole('button', { name: /add a condition/i }));
    fireEvent.change(screen.getByLabelText('When or unless'), { target: { value: 'unless' } });
    expect(latest.condition.rules[0].negate).toBe(true);
    expect(screen.getByText(/no movie or TV trailers are available/)).toBeInTheDocument();
  });

  test('removing the last rule clears the condition and its alternative', () => {
    render(<Harness initial={{
      condition: { match: 'all', rules: [{ kind: 'media_type', value: 'episode' }] },
      otherwise: { type: 'random', category_id: 4, count: 1 },
    }} />);
    fireEvent.click(screen.getByRole('button', { name: /remove rule/i }));
    expect(latest).toEqual({ condition: null, otherwise: null });
    expect(screen.getByRole('button', { name: /add a condition/i })).toBeInTheDocument();
  });
});

describe('genre rule', () => {
  test('choosing Genre starts empty, and typed genres become chips', () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole('button', { name: /add a condition/i }));
    fireEvent.change(screen.getByLabelText('Rule'), { target: { value: 'genre' } });
    expect(latest.condition.rules[0]).toEqual({ kind: 'genre', values: [] });
    expect(screen.getByText(/Jellyfin & Emby only/)).toBeInTheDocument();

    const input = screen.getByLabelText('Genre');
    fireEvent.change(input, { target: { value: 'Horror' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    fireEvent.change(input, { target: { value: 'horror' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(latest.condition.rules[0].values).toEqual(['Horror']); // no case-only duplicates

    fireEvent.click(screen.getByRole('button', { name: 'Remove Horror' }));
    expect(latest.condition.rules[0].values).toEqual([]);
  });

  test('genre wording and Jellyfin/Emby detection', () => {
    const condition = { rules: [{ kind: 'genre', values: ['Horror', 'Thriller'] }] };
    expect(describeCondition(condition)).toBe('the genre is Horror or Thriller');
    expect(describeCondition({ rules: [{ kind: 'genre', values: ['Horror'], negate: true }] }))
      .toBe('the genre is not Horror');
    expect(needsPlaybackInfo(condition)).toBe(true);
    expect(needsPlaybackInfo({ rules: [{ kind: 'time_window' }] })).toBe(false);
    expect(genresInSequence([
      { condition },
      { condition: { rules: [{ kind: 'genre', values: ['horror', 'Comedy'] }] } },
    ])).toEqual(['Horror', 'Thriller', 'Comedy']);
  });
});

describe('condition wording', () => {
  test('describes multiple rules with the match mode', () => {
    expect(describeCondition({
      match: 'any',
      rules: [
        { kind: 'trailers_available', source: 'movies', min: 3 },
        { kind: 'time_window', start: '22:00', end: '03:00', days: ['friday', 'saturday'] },
      ],
    })).toBe('at least 3 movie trailers are available or between 22:00 and 03:00 on Fri, Sat');
  });

  test('describes alternatives', () => {
    expect(describeOtherwise(null)).toBe('the block is skipped');
    expect(describeOtherwise({ type: 'nexup_trailers', count: 2 })).toBe('2 NeX-Up trailers play instead');
  });

  test('detects conditional blocks', () => {
    expect(blocksHaveConditions([{ type: 'random' }])).toBe(false);
    expect(blocksHaveConditions([{ type: 'random', condition: { rules: [{ kind: 'media_type' }] } }])).toBe(true);
  });
});
