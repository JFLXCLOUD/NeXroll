import React, { useState } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import SequenceConditionPanel from './SequenceConditionPanel';
import BlockConditionEditor from './BlockConditionEditor';
import { defaultCondition, describeCondition, needsPlaybackInfo } from '../utils/sequenceConditions';
import { sanitizeSequence, validateSequence } from '../utils/sequenceValidator';

test.each([SequenceConditionPanel, BlockConditionEditor])('both editors persist format and track scope', Editor => {
  let saved;
  function Harness() {
    const [value, setValue] = useState({ condition: defaultCondition(), otherwise: null });
    saved=value;
    return <Editor {...value} onChange={setValue} />;
  }
  render(<Harness />);
  const selector=screen.queryByLabelText('Rule 1') || screen.getByLabelText('Rule');
  fireEvent.change(selector,{target:{value:'audio_format'}});
  expect(screen.getByText(/Choose at least one audio format/)).toBeInTheDocument();
  fireEvent.click(screen.getByLabelText('Dolby TrueHD'));
  fireEvent.click(screen.getByLabelText('DTS / DTS-HD'));
  fireEvent.change(screen.getByLabelText('Audio track to check'),{target:{value:'any'}});
  const blocks=[{type:'library_trailers',count:1,...saved}];
  const restored=JSON.parse(JSON.stringify(sanitizeSequence(blocks)));
  expect(restored[0].condition.rules[0]).toMatchObject({kind:'audio_format',track:'any',values:['truehd','dts']});
  expect(needsPlaybackInfo(saved.condition)).toBe(true);
  expect(describeCondition(saved.condition)).toContain('any stored audio track');
  expect(validateSequence(restored).valid).toBe(true);
});

test('incomplete and malformed audio rules cannot silently save as unrestricted', () => {
  for (const rule of [{kind:'audio_format',values:[]}, {kind:'audio_format',values:['Atmos']}, {kind:'audio_format',values:['dts'],track:'selected'}]) {
    expect(validateSequence([{type:'library_trailers',condition:{rules:[rule]}}]).valid).toBe(false);
  }
  const legacy=[{type:'library_trailers',count:2}];
  expect(sanitizeSequence(legacy)[0]).not.toHaveProperty('condition');
});
