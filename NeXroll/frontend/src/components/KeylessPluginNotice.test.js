import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import KeylessPluginNotice from './KeylessPluginNotice';
import { keylessPlugins, pluginClientCount, pluginSeen } from '../utils/pluginClients';

const ROW = { server_type: 'Jellyfin', server_name: 'MEDIA-PC', address: '192.168.1.20', plugin_version: '1.14.2.0', last_seen: '2026-11-05T01:00:00Z' };

test('names the plugin and lets NeXroll give it a key when it can', () => {
  const onGiveKey = jest.fn();
  render(<KeylessPluginNotice server="Jellyfin" plugins={[ROW]} loginOn onGiveKey={onGiveKey} onOpenApiKeys={jest.fn()} />);
  expect(screen.getByText('The Jellyfin plugin on MEDIA-PC connects without an API key')).toBeInTheDocument();
  expect(screen.getByText(/A later version of NeXroll will require the key/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Give it a key' }));
  expect(onGiveKey).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole('button', { name: 'Open API Keys' })).not.toBeInTheDocument();
});

test('without a connection to the server it explains the manual steps', () => {
  const onOpenApiKeys = jest.fn();
  const rows = [ROW, { server_type: 'Emby', server_name: '', address: '192.168.1.40', last_seen: ROW.last_seen }];
  render(<KeylessPluginNotice server="Emby" plugins={rows} loginOn onOpenApiKeys={onOpenApiKeys} />);
  expect(screen.getByText('2 Emby plugins connect without an API key')).toBeInTheDocument();
  expect(screen.getByText('192.168.1.40')).toBeInTheDocument();
  expect(screen.getByText(/Settings > Plugins > NeXroll Intros/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Open API Keys' }));
  expect(onOpenApiKeys).toHaveBeenCalledTimes(1);
});

test('shows nothing with login off or no keyless plugin', () => {
  const { container, rerender } = render(<KeylessPluginNotice server="Jellyfin" plugins={[ROW]} loginOn={false} />);
  expect(container).toBeEmptyDOMElement();
  rerender(<KeylessPluginNotice server="Jellyfin" plugins={[]} loginOn />);
  expect(container).toBeEmptyDOMElement();
});

test('a plugin without a key counts as a working plugin', () => {
  expect(pluginSeen({ plugin_clients: [], keyless_plugins: [ROW] })).toBe(true);
  expect(pluginSeen({ plugin_clients: [] })).toBe(false);
  expect(pluginSeen(null)).toBe(false);
  expect(pluginClientCount({ plugin_clients: [{ api_key_name: 'k' }], keyless_plugins: [ROW] })).toBe(2);
  expect(keylessPlugins({ keyless_plugins: 'nonsense' })).toEqual([]);
});
