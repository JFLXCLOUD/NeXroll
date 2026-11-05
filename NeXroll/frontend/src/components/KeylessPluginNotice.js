import React from 'react';
import { KeyRound } from 'lucide-react';

/**
 * Connect page: a Jellyfin/Emby plugin asks for prerolls without an API key
 * while login is on. NeXroll still answers (the key is optional in both
 * plugins, and refusing would quietly stop prerolls), so the answer, the list
 * of preroll files with links to them, is open to anyone who can reach
 * NeXroll. A later version will require the key.
 *
 * Props: server ('Jellyfin' | 'Emby'), plugins (keyless_plugins rows),
 * loginOn, onGiveKey (NeXroll saves a key into the plugin itself; only when it
 * is connected to the server and found the plugin), giving, onOpenApiKeys.
 */
const SETTINGS_PATH = {
  Jellyfin: 'Dashboard > Plugins > NeXroll Intros',
  Emby: 'Settings > Plugins > NeXroll Intros',
};

const lastSeenLabel = (iso) => {
  const when = iso ? new Date(iso) : null;
  return when && !Number.isNaN(when.getTime()) ? when.toLocaleString() : '';
};

const where = (row) => row?.server_name || row?.address || '';

export default function KeylessPluginNotice({ server, plugins, loginOn, onGiveKey, giving = false, onOpenApiKeys }) {
  if (!loginOn || !Array.isArray(plugins) || plugins.length === 0) return null;
  const one = plugins.length === 1;
  const title = one
    ? `The ${server} plugin${where(plugins[0]) ? ` on ${where(plugins[0])}` : ''} connects without an API key`
    : `${plugins.length} ${server} plugins connect without an API key`;
  const last = lastSeenLabel(plugins[0]?.last_seen);

  return (
    <div className="nx-notice warn nx-keyless-notice" role="status" style={{ marginBottom: '1rem' }}>
      <strong><KeyRound size={14} aria-hidden="true" style={{ verticalAlign: 'middle', marginRight: '0.3rem' }} />{title}</strong>
      {!one && (
        <ul className="nx-keyless-list">
          {plugins.map((row, idx) => (
            <li key={`${row.server_name || ''}|${row.address || ''}|${idx}`}>
              {where(row) || server}{row.plugin_version ? ` (plugin ${row.plugin_version})` : ''}
            </li>
          ))}
        </ul>
      )}
      <p className="nx-keyless-text">
        Login is on, but NeXroll still gives {one ? 'it' : 'them'} prerolls without a key, so anyone who can reach
        NeXroll can list your prerolls the same way. A later version of NeXroll will require the key.
      </p>
      {onGiveKey ? (
        <>
          <p className="nx-keyless-text">
            NeXroll can create a key and save it in the plugin&apos;s settings. The plugin&apos;s other settings stay as they are.
          </p>
          <button type="button" className="button button-success" onClick={onGiveKey} disabled={giving}>
            {giving ? 'Saving the key...' : 'Give it a key'}
          </button>
        </>
      ) : (
        <>
          <ol className="nx-keyless-steps">
            <li>Create a key in Settings &gt; API Keys. Read Only is enough.</li>
            <li>In {server}, open {SETTINGS_PATH[server] || 'the NeXroll Intros plugin settings'}, paste it into API Key and save.</li>
          </ol>
          {onOpenApiKeys && (
            <button type="button" className="button" onClick={onOpenApiKeys}>Open API Keys</button>
          )}
        </>
      )}
      <p className="nx-keyless-foot">
        {last ? `Last request ${last}. ` : ''}This goes away once the plugin connects with a key, on its next playback.
      </p>
    </div>
  );
}
