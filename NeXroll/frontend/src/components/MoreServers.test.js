import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MoreServers } from './NexUpApprovedPages';

const reply = (value, ok = true) => Promise.resolve({ ok, json: async () => value });
let servers;
beforeEach(() => {
  servers = [{ id: 1, name: 'Radarr 4K', url: 'http://uhd:7879' }];
  global.fetch = jest.fn((url, options = {}) => {
    if (url === '/nexup/radarr/servers' && options.method === 'POST') {
      const body = JSON.parse(options.body);
      if (body.url === 'http://down') return reply({ success: false, message: 'Connection timed out' });
      servers = [...servers, { id: 2, name: body.name || 'Radarr 3', url: body.url }];
      return reply({ success: true, message: 'Connected to Radarr Kids (v6.0)', server: servers[1] });
    }
    if (url === '/nexup/radarr/servers/1' && options.method === 'DELETE') {
      servers = [];
      return reply({ success: true, message: 'Radarr 4K removed' });
    }
    if (url === '/nexup/radarr/servers/1/test') return reply({ success: false, message: 'Invalid API key' });
    if (url === '/nexup/radarr/servers') return reply({ servers });
    return reply({ servers: [] });
  });
});

test('lists the other servers and adds one after a failed attempt', async () => {
  const onChanged = jest.fn();
  render(<MoreServers kind="Radarr" onChanged={onChanged} />);
  expect(await screen.findByText('Radarr 4K')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /Add/ }));
  const connect = screen.getByRole('button', { name: /Connect/ });
  expect(connect).toBeDisabled();
  fireEvent.change(screen.getByPlaceholderText('http://localhost:7879'), { target: { value: 'http://down' } });
  fireEvent.change(screen.getByPlaceholderText("Enter this Radarr's API key"), { target: { value: 'k' } });
  fireEvent.click(connect);
  expect(await screen.findByRole('status')).toHaveTextContent('Connection timed out');
  expect(onChanged).not.toHaveBeenCalled();
  fireEvent.change(screen.getByPlaceholderText('Radarr 4K (optional)'), { target: { value: 'Radarr Kids' } });
  fireEvent.change(screen.getByPlaceholderText('http://localhost:7879'), { target: { value: 'http://kids:7880' } });
  fireEvent.click(screen.getByRole('button', { name: /Connect/ }));
  expect(await screen.findByText('Radarr Kids')).toBeInTheDocument();
  expect(screen.getByRole('status')).toHaveTextContent('Its movies are included from now on.');
  expect(onChanged).toHaveBeenCalledTimes(1);
  expect(screen.queryByPlaceholderText('http://localhost:7879')).not.toBeInTheDocument();
});

test('test reports the result and remove asks first', async () => {
  const onChanged = jest.fn();
  const confirm = jest.spyOn(window, 'confirm');
  render(<MoreServers kind="Radarr" onChanged={onChanged} />);
  await screen.findByText('Radarr 4K');
  fireEvent.click(screen.getByRole('button', { name: /Test/ }));
  expect(await screen.findByRole('status')).toHaveTextContent('Radarr 4K: Invalid API key');
  confirm.mockReturnValueOnce(false);
  fireEvent.click(screen.getByRole('button', { name: 'Remove Radarr 4K' }));
  expect(fetch.mock.calls.some(([, o]) => o?.method === 'DELETE')).toBe(false);
  confirm.mockReturnValueOnce(true);
  fireEvent.click(screen.getByRole('button', { name: 'Remove Radarr 4K' }));
  await waitFor(() => expect(screen.queryByText('Radarr 4K')).not.toBeInTheDocument());
  expect(onChanged).toHaveBeenCalledTimes(1);
  confirm.mockRestore();
});

test('the Sonarr list uses the Sonarr endpoints and wording', async () => {
  fetch.mockImplementation((url, options = {}) => {
    if (url === '/nexup/sonarr/servers' && options.method === 'POST') {
      return reply({ success: true, message: 'Connected to Sonarr-Anime (v4.0)', server: { id: 3, name: 'Sonarr-Anime', url: 'http://anime:8990' } });
    }
    return reply({ servers: url === '/nexup/sonarr/servers' && fetch.mock.calls.length > 1 ? [{ id: 3, name: 'Sonarr-Anime', url: 'http://anime:8990' }] : [] });
  });
  render(<MoreServers kind="Sonarr" />);
  expect(screen.getByRole('region', { name: 'More Sonarr servers' })).toHaveTextContent('A show in both appears once.');
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/nexup/sonarr/servers', undefined));
  fireEvent.click(screen.getByRole('button', { name: /Add/ }));
  fireEvent.change(screen.getByPlaceholderText('http://localhost:8990'), { target: { value: 'http://anime:8990' } });
  fireEvent.change(screen.getByPlaceholderText("Enter this Sonarr's API key"), { target: { value: 'k' } });
  fireEvent.click(screen.getByRole('button', { name: /Connect/ }));
  expect(await screen.findByText('Sonarr-Anime')).toBeInTheDocument();
  expect(screen.getByRole('status')).toHaveTextContent('Its shows are included from now on.');
  expect(fetch.mock.calls.every(([url]) => url.startsWith('/nexup/sonarr/'))).toBe(true);
});
