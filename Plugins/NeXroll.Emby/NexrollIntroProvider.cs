using System.Net.Http.Json;
using System.Security.Cryptography;
using System.Text;
using MediaBrowser.Controller.Entities;
using MediaBrowser.Controller.Entities.Movies;
using MediaBrowser.Controller.Entities.TV;
using MediaBrowser.Controller.Library;
using MediaBrowser.Model.Logging;

namespace NeXroll.Emby;

/// <summary>
/// Emby intro provider that fetches preroll paths from a NeXroll server.
/// Downloads all available intros to a local cache so Emby can register them
/// as library items (via GetAllIntroFiles / "Refresh Custom Intros" task).
/// At playback time, GetIntros selects which cached intros to play.
/// </summary>
public class NexrollIntroProvider : IIntroProvider
{
    private readonly ILogger _logger;
    private static readonly HttpClient _httpClient = new();
    private static readonly string _cacheDir = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "NeXroll", "intro_cache");

    /// <summary>Lock to avoid concurrent cache syncs.</summary>
    private static readonly SemaphoreSlim _syncLock = new(1, 1);
    /// <summary>Last time we synced the cache from NeXroll.</summary>
    private static DateTime _lastCacheSync = DateTime.MinValue;
    /// <summary>Minimum interval between full cache syncs.</summary>
    private static readonly TimeSpan _cacheSyncInterval = TimeSpan.FromMinutes(10);

    public string Name => "NeXroll Intros";

    public NexrollIntroProvider(ILogManager logManager)
    {
        _logger = logManager.GetLogger("NeXroll");
    }

    /// <summary>
    /// Build an HttpRequestMessage with NeXroll plugin identification headers.
    /// </summary>
    private static HttpRequestMessage BuildRequest(HttpMethod method, string url, PluginConfiguration config)
    {
        var request = new HttpRequestMessage(method, url);

        if (!string.IsNullOrWhiteSpace(config.ApiKey))
        {
            request.Headers.Add("X-Api-Key", config.ApiKey.Trim());
        }

        request.Headers.Add("X-Plugin-Server-Type", "Emby");

        try
        {
            request.Headers.Add("X-Plugin-Server-Name", Environment.MachineName);
        }
        catch { /* ignore */ }

        request.Headers.Add("X-Plugin-Server-Version",
            typeof(NexrollIntroProvider).Assembly.GetName().Version?.ToString() ?? "1.0.0");

        return request;
    }

    public async Task<IEnumerable<IntroInfo>> GetIntros(BaseItem item, User user)
    {
        var config = Plugin.Instance?.Configuration;
        if (config is null || string.IsNullOrWhiteSpace(config.NexrollUrl))
        {
            return Enumerable.Empty<IntroInfo>();
        }

        string mediaType;
        if (item is Movie)
        {
            if (!config.EnableForMovies) return Enumerable.Empty<IntroInfo>();
            mediaType = "Movie";
        }
        else if (item is Episode)
        {
            if (!config.EnableForEpisodes) return Enumerable.Empty<IntroInfo>();
            mediaType = "Episode";
        }
        else
        {
            return Enumerable.Empty<IntroInfo>();
        }

        try
        {
            // Ensure the cache is populated so GetAllIntroFiles returns files
            await SyncCacheIfNeeded(config).ConfigureAwait(false);

            var baseUrl = config.NexrollUrl.TrimEnd('/');
            var url = $"{baseUrl}/plugin/intros?media_type={Uri.EscapeDataString(mediaType)}&item_id={Uri.EscapeDataString(item.Id.ToString())}";

            using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(
                config.TimeoutSeconds > 0 ? config.TimeoutSeconds : 5));

            using var request = BuildRequest(HttpMethod.Get, url, config);
            using var httpResponse = await _httpClient.SendAsync(request, cts.Token).ConfigureAwait(false);
            httpResponse.EnsureSuccessStatusCode();

            var response = await httpResponse.Content.ReadFromJsonAsync<NexrollIntroResponse>(cancellationToken: cts.Token)
                .ConfigureAwait(false);

            if (response?.Items is null || response.Items.Count == 0)
            {
                return Enumerable.Empty<IntroInfo>();
            }

            // Default to 1 intro when MaxIntros is 0 (unset)
            var maxCount = config.MaxIntros > 0 ? config.MaxIntros : 1;

            var items = response.Items;
            if (string.Equals(response.Mode, "shuffle", StringComparison.OrdinalIgnoreCase))
            {
                items = items.OrderBy(_ => Random.Shared.Next()).ToList();
            }

            var intros = new List<IntroInfo>();
            foreach (var intro in items.Take(maxCount))
            {
                var localPath = GetCachedPath(intro);
                if (!string.IsNullOrWhiteSpace(localPath) && File.Exists(localPath))
                {
                    intros.Add(new IntroInfo { Path = localPath });
                }
            }

            _logger.Info(
                "NeXroll: Injecting {0} intro(s) before {1} '{2}'",
                intros.Count, mediaType, item.Name);

            return intros;
        }
        catch (TaskCanceledException)
        {
            _logger.Warn("NeXroll server request timed out ({0}s)", config.TimeoutSeconds);
            return Enumerable.Empty<IntroInfo>();
        }
        catch (HttpRequestException ex)
        {
            _logger.Warn("Failed to reach NeXroll server at {0}: {1}", config.NexrollUrl, ex.Message);
            return Enumerable.Empty<IntroInfo>();
        }
        catch (Exception ex)
        {
            _logger.Error("Unexpected error fetching intros from NeXroll: {0}", ex.Message);
            return Enumerable.Empty<IntroInfo>();
        }
    }

    /// <summary>
    /// Returns all cached intro file paths so Emby can register them as
    /// library items during "Refresh Custom Intros". This is essential —
    /// Emby will only play intros that are recognised library items.
    /// </summary>
    public IEnumerable<string> GetAllIntroFiles()
    {
        // Kick off a background cache sync if needed (fire-and-forget)
        _ = Task.Run(async () =>
        {
            try
            {
                var config = Plugin.Instance?.Configuration;
                if (config is not null && !string.IsNullOrWhiteSpace(config.NexrollUrl))
                {
                    await SyncCacheIfNeeded(config).ConfigureAwait(false);
                }
            }
            catch { /* swallow — best effort */ }
        });

        if (!Directory.Exists(_cacheDir))
            return Enumerable.Empty<string>();

        return Directory.EnumerateFiles(_cacheDir)
            .Where(f =>
            {
                var ext = Path.GetExtension(f).ToLowerInvariant();
                return ext is ".mp4" or ".mkv" or ".avi" or ".mov" or ".wmv" or ".webm";
            });
    }

    /// <summary>
    /// Sync all available prerolls from NeXroll into the local cache.
    /// Called before GetIntros and from GetAllIntroFiles background task.
    /// </summary>
    private async Task SyncCacheIfNeeded(PluginConfiguration config)
    {
        if (DateTime.UtcNow - _lastCacheSync < _cacheSyncInterval)
            return;

        if (!await _syncLock.WaitAsync(0).ConfigureAwait(false))
            return; // another sync already in progress

        try
        {
            if (DateTime.UtcNow - _lastCacheSync < _cacheSyncInterval)
                return;

            var baseUrl = config.NexrollUrl.TrimEnd('/');
            var url = $"{baseUrl}/plugin/intros?media_type=Movie&item_id=0";

            using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(30));
            using var request = BuildRequest(HttpMethod.Get, url, config);
            using var httpResponse = await _httpClient.SendAsync(request, cts.Token).ConfigureAwait(false);
            httpResponse.EnsureSuccessStatusCode();

            var response = await httpResponse.Content.ReadFromJsonAsync<NexrollIntroResponse>(cancellationToken: cts.Token)
                .ConfigureAwait(false);

            if (response?.Items is null || response.Items.Count == 0)
            {
                _lastCacheSync = DateTime.UtcNow;
                return;
            }

            Directory.CreateDirectory(_cacheDir);
            var downloadCount = 0;

            foreach (var intro in response.Items)
            {
                try
                {
                    var cached = GetCachedPath(intro);
                    if (cached is null) continue;
                    if (File.Exists(cached)) continue;

                    if (string.IsNullOrWhiteSpace(intro.StreamUrl)) continue;

                    using var dlCts = new CancellationTokenSource(TimeSpan.FromSeconds(60));
                    using var dlResp = await _httpClient.GetAsync(intro.StreamUrl,
                        HttpCompletionOption.ResponseHeadersRead, dlCts.Token).ConfigureAwait(false);
                    dlResp.EnsureSuccessStatusCode();

                    var tmpPath = cached + ".tmp";
                    await using (var fs = new FileStream(tmpPath, FileMode.Create, FileAccess.Write, FileShare.None))
                    {
                        await dlResp.Content.CopyToAsync(fs, dlCts.Token).ConfigureAwait(false);
                    }

                    File.Move(tmpPath, cached, overwrite: true);
                    downloadCount++;
                }
                catch (Exception ex)
                {
                    _logger.Debug("NeXroll: Cache sync — failed to download '{0}': {1}", intro.Name, ex.Message);
                }
            }

            if (downloadCount > 0)
            {
                _logger.Info("NeXroll: Cache sync — downloaded {0} new intro(s), {1} total in cache",
                    downloadCount, Directory.GetFiles(_cacheDir).Length);
            }

            _lastCacheSync = DateTime.UtcNow;
        }
        catch (Exception ex)
        {
            _logger.Debug("NeXroll: Cache sync error: {0}", ex.Message);
        }
        finally
        {
            _syncLock.Release();
        }
    }

    /// <summary>
    /// Get the expected local cache path for an intro item.
    /// </summary>
    private static string? GetCachedPath(NexrollIntroItem intro)
    {
        if (string.IsNullOrWhiteSpace(intro.Path)) return null;

        var ext = Path.GetExtension(intro.Path);
        if (string.IsNullOrEmpty(ext)) ext = ".mp4";
        var hash = SHA256Hash(intro.Path);
        return Path.Combine(_cacheDir, $"{hash}{ext}");
    }

    private static string TranslatePath(string path, PluginConfiguration config)
    {
        if (string.IsNullOrWhiteSpace(path)) return path;

        if (!string.IsNullOrWhiteSpace(config.PathPrefixFrom)
            && !string.IsNullOrWhiteSpace(config.PathPrefixTo))
        {
            var from = config.PathPrefixFrom.TrimEnd('/', '\\');
            var to = config.PathPrefixTo.TrimEnd('/', '\\');

            var normPath = path.Replace('\\', '/');
            var normFrom = from.Replace('\\', '/');

            if (normPath.StartsWith(normFrom, StringComparison.OrdinalIgnoreCase))
            {
                var rest = normPath[normFrom.Length..];
                if (to.Contains('\\'))
                    rest = rest.Replace('/', '\\');
                else
                    rest = rest.Replace('\\', '/');
                return to + rest;
            }
        }

        return path;
    }

    private sealed class NexrollIntroResponse
    {
        public List<NexrollIntroItem> Items { get; set; } = new();
        public int TotalRecordCount { get; set; }
        public string Mode { get; set; } = "shuffle";
    }

    private sealed class NexrollIntroItem
    {
        public string Path { get; set; } = string.Empty;
        public string Name { get; set; } = string.Empty;
        public string StreamUrl { get; set; } = string.Empty;
    }

    private static string SHA256Hash(string input)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(input));
        return Convert.ToHexString(bytes).ToLowerInvariant();
    }
}
