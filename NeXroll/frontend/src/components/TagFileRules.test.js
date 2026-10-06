import React, { useState } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import BlockConditionEditor from './BlockConditionEditor';
import SequenceConditionPanel from './SequenceConditionPanel';
import { describeCondition, needsPlaybackInfo, ruleValuesInSequence } from '../utils/sequenceConditions';
import { validateBlock } from '../utils/sequenceValidator';

const categories = [{ id: 4, name: 'IMAX Intros' }, { id: 2, name: 'House Intros' }];

let latest;
const Harness = ({ Editor = BlockConditionEditor }) => {
  const [value, setValue] = useState({ condition: null, otherwise: null });
  latest = value;
  return <Editor condition={value.condition} otherwise={value.otherwise} onChange={setValue} categories={categories} />;
};

const addChip = (label, text) => {
  const input = screen.getByLabelText(label);
  fireEvent.change(input, { target: { value: text } });
  fireEvent.keyDown(input, { key: 'Enter' });
};

describe('tag rule', () => {
  test('starts empty and collects tags without case-only duplicates', () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole('button', { name: /add a condition/i }));
    fireEvent.change(screen.getByLabelText('Rule'), { target: { value: 'tag' } });
    expect(latest.condition.rules[0]).toEqual({ kind: 'tag', values: [] });
    addChip('Tag', 'IMAX');
    addChip('Tag', 'imax');
    expect(latest.condition.rules[0].values).toEqual(['IMAX']);
    expect(screen.getByText(/the tag is IMAX/)).toBeInTheDocument();
  });

  test('works in the Sequence Builder panel too', () => {
    render(<Harness Editor={SequenceConditionPanel} />);
    fireEvent.click(screen.getByRole('button', { name: /add a condition/i }));
    fireEvent.change(screen.getByLabelText('Rule 1'), { target: { value: 'tag' } });
    addChip('Tag', 'IMAX');
    expect(latest.condition.rules[0]).toEqual({ kind: 'tag', values: ['IMAX'] });
    expect(screen.getByText('Any of these tags')).toBeInTheDocument();
  });
});

describe('file path rule', () => {
  test('collects text to look for', () => {
    render(<Harness Editor={SequenceConditionPanel} />);
    fireEvent.click(screen.getByRole('button', { name: /add a condition/i }));
    fireEvent.change(screen.getByLabelText('Rule 1'), { target: { value: 'file_name' } });
    expect(latest.condition.rules[0]).toEqual({ kind: 'file_name', values: [] });
    addChip('Text in the file path', 'IMAX');
    expect(latest.condition.rules[0].values).toEqual(['IMAX']);
    expect(screen.getByText(/the file path contains "IMAX"/)).toBeInTheDocument();
  });

  test('wording, negation and Jellyfin/Emby detection', () => {
    expect(describeCondition({ rules: [{ kind: 'file_name', values: ['IMAX', 'Remux'] }] }))
      .toBe('the file path contains "IMAX" or "Remux"');
    expect(describeCondition({ rules: [{ kind: 'file_name', values: ['IMAX'], negate: true }] }))
      .toBe('the file path doesn\'t contain "IMAX"');
    expect(describeCondition({ rules: [{ kind: 'tag', values: ['IMAX'], negate: true }] }))
      .toBe('the tag is not IMAX');
    expect(needsPlaybackInfo({ rules: [{ kind: 'tag', values: ['IMAX'] }] })).toBe(true);
    expect(needsPlaybackInfo({ rules: [{ kind: 'file_name', values: ['IMAX'] }] })).toBe(true);
  });
});

test('the preview offers the tags a sequence names', () => {
  expect(ruleValuesInSequence([
    { condition: { rules: [{ kind: 'tag', values: ['IMAX'] }, { kind: 'genre', values: ['Horror'] }] } },
    { condition: { rules: [{ kind: 'tag', values: ['imax', '3D'] }] } },
  ], 'tag')).toEqual(['IMAX', '3D']);
});

describe('validation', () => {
  const block = (rule) => ({ type: 'random', category_id: 4, count: 1, condition: { match: 'all', rules: [rule] } });

  test('an empty tag or file path rule cannot be saved', () => {
    expect(validateBlock(block({ kind: 'tag', values: [] }), categories)).toContain('Add at least one tag');
    expect(validateBlock(block({ kind: 'file_name', values: [' '] }), categories))
      .toContain('Add some text for the file path to contain');
  });

  test('filled rules are valid', () => {
    expect(validateBlock(block({ kind: 'tag', values: ['IMAX'] }), categories)).toEqual([]);
    expect(validateBlock(block({ kind: 'file_name', values: ['IMAX'] }), categories)).toEqual([]);
  });
});
