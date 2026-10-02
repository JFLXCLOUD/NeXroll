import React, { useState } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import TrailerGenreMatch from './TrailerGenreMatch';
import BlockEditor from './BlockEditor';
import { sanitizeSequence } from '../utils/sequenceValidator';
import { genreMatchSummary } from '../utils/trailerRatings';

test('choosing "play no trailers" sets only, and switching off clears it', () => {
  let current;
  function Harness() {
    const [value, setValue] = useState({});
    current = value;
    return <TrailerGenreMatch value={value} onChange={patch => setValue(v => ({ ...v, ...patch }))} />;
  }
  render(<Harness />);
  expect(screen.queryByLabelText(/When no trailer shares its genre/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByLabelText("Same genre as the movie that's starting"));
  expect(current).toEqual({ match_playing: true, match_playing_only: false });
  expect(screen.getByText(/on Plex trailers come from the whole selection/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText(/When no trailer shares its genre/), { target: { value: 'only' } });
  expect(current).toEqual({ match_playing: true, match_playing_only: true });
  expect(screen.getByText(/on Plex this block plays nothing/)).toBeInTheDocument();
  fireEvent.click(screen.getByLabelText("Same genre as the movie that's starting"));
  expect(current).toEqual({ match_playing: false, match_playing_only: false });
});

test('the fields survive saving; old NeX-Up blocks stay unchanged', () => {
  const [saved] = sanitizeSequence([{ type: 'nexup_trailers', count: 2, match_playing: true, match_playing_only: true }]);
  expect(saved).toMatchObject({ match_playing: true, match_playing_only: true });
  expect(sanitizeSequence([{ type: 'nexup_trailers', count: 2 }])[0]).not.toHaveProperty('match_playing');
  expect(genreMatchSummary(saved)).toBe("only the movie's genre");
  expect(genreMatchSummary({ match_playing: true })).toBe('same genre as the movie');
  expect(genreMatchSummary({ match_playing_only: true })).toBe('');
});

test('legacy modal editor saves and reopens a genre-matched NeX-Up block', () => {
  const onSave = jest.fn();
  const props = { categories: [], prerolls: [], isNew: false, onSave, onCancel: jest.fn() };
  const { unmount } = render(<BlockEditor {...props} block={{ id: 'a', type: 'nexup_trailers', count: 2 }} />);
  fireEvent.click(screen.getByLabelText("Same genre as the movie that's starting"));
  fireEvent.change(screen.getByLabelText(/When no trailer shares its genre/), { target: { value: 'only' } });
  fireEvent.click(screen.getByRole('button', { name: /save|update block/i }));
  const saved = onSave.mock.calls[0][0];
  expect(saved).toMatchObject({ type: 'nexup_trailers', match_playing: true, match_playing_only: true });
  unmount();
  render(<BlockEditor {...props} block={saved} />);
  expect(screen.getByLabelText("Same genre as the movie that's starting")).toBeChecked();
  expect(screen.getByLabelText(/When no trailer shares its genre/)).toHaveValue('only');
});
