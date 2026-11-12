import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import NexUpApprovedPages from './NexUpApprovedPages';

// The Include unmonitored switches were left behind on the old settings page
// when NeX-Up was rebuilt for 2.2.0, so the settings could no longer be changed.
const openSettings = settings => {
  const onUpdateSettings = jest.fn();
  render(<NexUpApprovedPages activeTab="nexup/settings" settings={{ storage_path: 'C:/trailers', ...settings }}
    storage={{ total_size_gb: 1.2 }} potoken={{ status: {} }} youtubeSetup={{ status: {} }}
    onUpdateSettings={onUpdateSettings} onOpenFolder={() => {}} onTestPotoken={() => {}}
    onConfigureYoutube={() => {}} onInstallPotoken={() => {}} onTestTmdbKey={() => {}} />);
  return onUpdateSettings;
};

test('unmonitored movies and shows can be turned on from the Settings page', () => {
  const onUpdateSettings = openSettings({});
  const movies = screen.getByRole('switch', { name: 'Include unmonitored movies' });
  const shows = screen.getByRole('switch', { name: 'Include unmonitored TV shows' });
  expect(movies).toHaveAttribute('aria-checked', 'false');
  expect(shows).toHaveAttribute('aria-checked', 'false');
  fireEvent.click(movies);
  expect(onUpdateSettings).toHaveBeenCalledWith({ include_unmonitored_movies: true });
  fireEvent.click(shows);
  expect(onUpdateSettings).toHaveBeenCalledWith({ include_unmonitored_shows: true });
});

test('the switches show the saved values and turn them off', () => {
  const onUpdateSettings = openSettings({ include_unmonitored_movies: true, include_unmonitored_shows: true });
  const movies = screen.getByRole('switch', { name: 'Include unmonitored movies' });
  expect(movies).toHaveAttribute('aria-checked', 'true');
  expect(screen.getByRole('switch', { name: 'Include unmonitored TV shows' })).toHaveAttribute('aria-checked', 'true');
  fireEvent.click(movies);
  expect(onUpdateSettings).toHaveBeenCalledWith({ include_unmonitored_movies: false });
});
