import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import NexUpApprovedPages from './NexUpApprovedPages';

// The Upcoming page shows which titles are already in the library ("Available
// Now!" on the Coming Soon list) instead of flagging their trailer as
// missing, and every title can be left off the list, trailer or not: list
// exclusions are kept per title now, so they outlive the trailer.
const soon = new Date(Date.now() + 5 * 86400000).toISOString().slice(0, 10);
const movies = [
  { radarr_id: 1, tmdb_id: 11, title: 'In The Library', release_date: soon, trailer_url: 'yt1', downloaded: false, available_now: true, excluded_from_list: false, monitored: true },
  { radarr_id: 2, tmdb_id: 22, title: 'Still Coming', release_date: soon, trailer_url: 'yt2', downloaded: false, available_now: false, excluded_from_list: false, monitored: true },
  { radarr_id: 3, tmdb_id: 33, title: 'Arrived With Trailer', release_date: soon, trailer_url: 'yt3', downloaded: true, available_now: true, excluded_from_list: false, monitored: true },
];

const renderPage = (overrides = {}) => {
  const props = {
    activeTab: 'nexup/upcoming',
    settings: { radarr_connected: true, sonarr_connected: true },
    upcomingMovies: movies, upcomingShows: [], upcomingTab: 'movies', setUpcomingTab: () => {},
    calendarMonth: new Date(), setCalendarMonth: () => {}, downloadingId: null,
    onRefreshMovies: () => {}, onRefreshShows: () => {}, onDownloadMovie: () => {}, onDownloadShow: () => {},
    onToggleExclude: jest.fn(), onNavigate: () => {}, movieTrailers: [], tvTrailers: [], onPlayTrailer: () => {},
    ...overrides,
  };
  render(<NexUpApprovedPages {...props} />);
  return props;
};

beforeEach(() => { try { localStorage.removeItem('nexupUpcomingView'); } catch (_) { /* no storage */ } });

const row = title => screen.getAllByRole('article').find(article => within(article).queryByText(title));

test('a title already in the library reads Available now, not Trailer Missing', () => {
  renderPage();
  const library = row('In The Library');
  expect(within(library).getByText('Available now')).toBeInTheDocument();
  expect(within(library).queryByText('Trailer Missing')).not.toBeInTheDocument();
  expect(within(library).getByRole('button', { name: /Download/ })).toBeEnabled();
  const arrived = row('Arrived With Trailer');
  expect(within(arrived).getByText('Available now')).toBeInTheDocument();
  expect(within(arrived).getByRole('button', { name: 'Preview' })).toBeInTheDocument();
  const coming = row('Still Coming');
  expect(within(coming).getByText('Trailer Missing')).toBeInTheDocument();
  expect(within(coming).queryByText('Available now')).not.toBeInTheDocument();
});

test('every title can be excluded from the list, with or without a trailer', () => {
  const { onToggleExclude } = renderPage();
  const toggles = screen.getAllByRole('button', { name: 'Exclude from list' });
  expect(toggles).toHaveLength(3);
  fireEvent.click(toggles[1]);
  expect(onToggleExclude).toHaveBeenCalledWith(expect.objectContaining({ tmdb_id: 22 }), 'movie');
});
