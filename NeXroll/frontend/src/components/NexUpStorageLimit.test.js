import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import NexUpApprovedPages from './NexUpApprovedPages';

// NeX-Up > Settings showed the storage bar but had no control for the limit
// (only the old settings page did), so it stayed at the 5 GB default.
const openSettings = settings => {
  const onUpdateSettings = jest.fn();
  render(<NexUpApprovedPages activeTab="nexup/settings" settings={{ storage_path: 'C:/trailers', ...settings }}
    storage={{ total_size_gb: 1.2 }} potoken={{ status: {} }} youtubeSetup={{ status: {} }}
    onUpdateSettings={onUpdateSettings} onOpenFolder={() => {}} onTestPotoken={() => {}}
    onConfigureYoutube={() => {}} onInstallPotoken={() => {}} onTestTmdbKey={() => {}} />);
  return onUpdateSettings;
};

test('the storage limit can be changed on the Settings page', () => {
  const onUpdateSettings = openSettings({ max_storage_gb: 5 });
  const limit = screen.getByRole('combobox', { name: 'Storage limit' });
  expect(limit).toHaveValue('5');
  expect(screen.getByText('1.2 / 5 GB')).toBeInTheDocument();
  fireEvent.change(limit, { target: { value: '20' } });
  expect(onUpdateSettings).toHaveBeenCalledWith({ max_storage_gb: 20 });
});

test('a limit saved some other way stays selectable', () => {
  openSettings({ max_storage_gb: 7.5 });
  const limit = screen.getByRole('combobox', { name: 'Storage limit' });
  expect(limit).toHaveValue('7.5');
  expect(screen.getByRole('option', { name: '7.5 GB' })).toBeInTheDocument();
});
