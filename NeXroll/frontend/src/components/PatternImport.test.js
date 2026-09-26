import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import PatternImport from './PatternImport';

const respond = body => Promise.resolve({ ok: true, json: async () => body });

const categories = [{ id: 1, name: 'Halloween' }, { id: 2, name: "Kids' Night" }, { id: 3, name: 'Imported' }];

function pick(file) {
  const input = document.querySelector('input[type=file]');
  fireEvent.change(input, { target: { files: [file] } });
}

test('hands the parent one object with the blocks, name and description', async () => {
  // The Library read this callback as (blocks, metadata) and posted the whole
  // object as `blocks`, so every import was refused by the server.
  const blocks = [{ type: 'random', category_id: 1, count: 2 }];
  global.fetch = jest.fn(url => (String(url).includes('/categories')
    ? respond(categories)
    : respond({ pattern_name: 'Friday Night', pattern_description: 'Scary', created_by: 'NeXroll', blocks,
      match_results: { matched: 1, unmatched: 0, downloadable: 0, total_blocks: 1, missing_categories: [], missing_prerolls: [] } })));
  const onImport = jest.fn();
  render(<PatternImport isOpen onClose={() => {}} onImport={onImport} />);
  pick(new File(['{}'], 'friday.nexseq', { type: 'application/json' }));
  fireEvent.click(screen.getByRole('button', { name: /Preview Import/ }));
  fireEvent.click(await screen.findByRole('button', { name: /Import Pattern/ }));
  expect(onImport).toHaveBeenCalledTimes(1);
  expect(onImport.mock.calls[0]).toHaveLength(1);
  expect(onImport.mock.calls[0][0]).toMatchObject({ blocks, name: 'Friday Night', description: 'Scary' });
});

test("a bundle's fixed preroll goes to its own category by default, not the first one listed", async () => {
  global.fetch = jest.fn((url, options) => {
    if (String(url).includes('/categories')) return respond(categories);
    return respond({
      pattern_name: 'Bundle', blocks: [],
      bundle_preview: {
        categories: [{ name: "Kids' Night", folder: "Kids' Night", preroll_count: 1, files: ['Welcome'] }],
        fixed: [{ name: 'Welcome.mp4', filename: 'Welcome.mp4', original_category: "Kids' Night" },
                { name: 'Loose.mp4', filename: 'Loose.mp4' }],
        sequence: [], preview_id: 'abc12345',
      },
      match_results: { matched: 0, unmatched: 0, downloadable: 0, total_blocks: 0, missing_categories: [], missing_prerolls: [] },
    });
  });
  render(<PatternImport isOpen onClose={() => {}} onImport={() => {}} />);
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/categories'));
  pick(new File(['zip'], 'bundle.zip', { type: 'application/zip' }));
  fireEvent.click(screen.getByRole('button', { name: /Preview Import/ }));
  fireEvent.click(await screen.findByRole('button', { name: /Import with Mappings/ }));
  const sent = fetch.mock.calls.find(([, o]) => o && o.body instanceof FormData && o.body.get('folder_mappings'));
  const mappings = JSON.parse(sent[1].body.get('folder_mappings'));
  expect(mappings["category:Kids' Night"]).toBe(2);
  expect(mappings['fixed:Welcome.mp4']).toBe(2);
  expect(mappings['fixed:Loose.mp4']).toBe(3);
});
