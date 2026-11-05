/**
 * Jellyfin/Emby plugins NeXroll has heard from, from /jellyfin/status or
 * /emby/status. `plugin_clients` lists plugins that sent an API key;
 * `keyless_plugins` the ones asking for prerolls without one (the key is
 * optional in both plugins). Both are working plugins: the Emby panel used to
 * say "the plugin is missing" for a keyless one that was playing prerolls.
 */

export const keylessPlugins = (info) => (Array.isArray(info?.keyless_plugins) ? info.keyless_plugins : []);

export const keyedPlugins = (info) => (Array.isArray(info?.plugin_clients) ? info.plugin_clients : []);

/** How many plugins of this server have reached NeXroll, with or without a key. */
export const pluginClientCount = (info) => keyedPlugins(info).length + keylessPlugins(info).length;

export const pluginSeen = (info) => pluginClientCount(info) > 0;
