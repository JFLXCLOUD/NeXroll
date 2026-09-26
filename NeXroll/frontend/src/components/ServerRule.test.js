import React, { useState } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import BlockConditionEditor from './BlockConditionEditor';
import SequenceConditionPanel from './SequenceConditionPanel';
import { describeBlockCondition, describeRule, needsPlaybackInfo } from '../utils/sequenceConditions';
import { validateBlock } from '../utils/sequenceValidator';

const categories = [{ id: 1, name: 'Halloween Jellyfin' }, { id: 2, name: 'Halloween Plex' }];

let latest;
const Harness = ({ Editor }) => {
  const [value, setValue] = useState({ condition: null, otherwise: null });
  latest = value;
  return <Editor condition={value.condition} otherwise={value.otherwise} onChange={setValue} categories={categories} />;
};

test.each([
  ['the schedule form', BlockConditionEditor, 'Rule'],
  ['the Sequence Builder', SequenceConditionPanel, 'Rule 1'],
])('%s can limit a block to chosen media servers', (_, Editor, ruleLabel) => {
  render(<Harness Editor={Editor} />);
  fireEvent.click(screen.getByRole('button', { name: /add a condition/i }));
  fireEvent.change(screen.getByLabelText(ruleLabel), { target: { value: 'server' } });
  expect(latest.condition.rules[0]).toEqual({ kind: 'server', values: ['jellyfin'] });
  fireEvent.click(screen.getByLabelText('Emby'));
  expect(latest.condition.rules[0].values).toEqual(['jellyfin', 'emby']);
  fireEvent.click(screen.getByLabelText('Jellyfin'));
  fireEvent.click(screen.getByLabelText('Emby'));
  expect(screen.getByText('Choose at least one server before saving.')).toBeInTheDocument();
});

test('the rule reads as a sentence and is not a Jellyfin-only playback rule', () => {
  expect(describeRule({ kind: 'server', values: ['jellyfin', 'emby'] })).toBe('playing on Jellyfin or Emby');
  expect(describeRule({ kind: 'server', values: ['plex'], negate: true })).toBe('not playing on Plex');
  const condition = { match: 'all', rules: [{ kind: 'server', values: ['jellyfin'] }] };
  expect(needsPlaybackInfo(condition)).toBe(false);
  expect(describeBlockCondition(condition, { type: 'random', category_id: 2, count: 1 }, id => categories.find(c => c.id === id).name))
    .toBe('Plays only when playing on Jellyfin. Otherwise, 1 preroll from Halloween Plex play instead.');
});

test('a server rule must name a server', () => {
  const block = { type: 'random', category_id: 1, count: 1 };
  expect(validateBlock({ ...block, condition: { rules: [{ kind: 'server', values: [] }] } }, categories))
    .toContain('Choose at least one media server');
  expect(validateBlock({ ...block, condition: { rules: [{ kind: 'server', values: ['kodi'] }] } }, categories))
    .toContain('Choose at least one media server');
  expect(validateBlock({ ...block, condition: { rules: [{ kind: 'server', values: ['plex'] }] } }, categories))
    .not.toContain('Choose at least one media server');
});
