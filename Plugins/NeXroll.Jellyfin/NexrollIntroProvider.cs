using System.Net.Http.Json;
using System.Net.Http.Headers;
using System.Security.Cryptography;
using System.Text;
using Jellyfin.Database.Implementations.Entities;
using MediaBrowser.Controller.Entities;
using MediaBrowser.Controller.Entities.Movies;
using MediaBrowser.Controller.Entities.TV;
using MediaBrowser.Controller.Library;
using MediaBrowser.Model.Dto;
using MediaBrowser.Model.IO;
using Microsoft.Extensions.Logging;

namespace NeXroll.Jellyfin;

/// <summary>
/// Jellyfin intro provider that fetches the currently-active preroll
/// paths from a NeXroll server and returns them as <see cref="IntroInfo"/>
/// items for playback injection.
///
/// Jellyfin's <c>ResolveIntro</c> requires intro files to exist in its
/// database as Video items.  This provider downloads preroll files to a
/// local cache, resolves them via <c>ILibraryManager.ResolvePath</c>, and
/// saves them to the database so they can be returned by <c>ItemId</c>.
/// </summary>
public class NexrollIntroProvider : IIntroProvider
{
    private readonly ILogger<NexrollIntroProvider> _logger;
    private readonly ILibraryManager _libraryManager;
    private readonly IFileSystem _fileSystem;
    private static readonly HttpClient _httpClient = new();

    /// <summary>
    /// Resolve an absolute, writable directory for cached intro downloads.
    ///
    /// Previously this used <c>Environment.GetFolderPath(LocalApplicationData)</c>,
    /// but on Linux/.NET that resolves via <c>$XDG_DATA_HOME</c> or
    /// <c>$HOME/.local/share</c> and returns an EMPTY string when <c>HOME</c> is
    /// unset — exactly the case for the Jellyfin service under s6-overlay
    /// (linuxserver.io Docker on Unraid, etc.). An empty base collapses
    /// <c>Path.Combine</c> to a RELATIVE path, which <c>Directory.CreateDirectory</c>
    /// then resolves against the process working directory (the s6 service dir),
    /// throwing <c>UnauthorizedAccessException</c>. See GitHub issue #30.
    ///
    /// We use Jellyfin's own plugin data folder (absolute and writable, under the
    /// server config dir) and fall back to the OS temp directory if that is
    /// unavailable or not rooted, so the path can never collapse to a relative
    /// one again.
    /// </summary>
    private static string GetCacheDir()
    {
        string? baseDir = null;
        try
        {
            baseDir = Plugin.Instance?.DataFolderPath;
        }
        catch
        {
            // Fall through to the temp-dir fallback below.
        }

        if (string.IsNullOrWhiteSpace(baseDir) || !Path.IsPathRooted(baseDir))
        {
            baseDir = Path.Combine(Path.GetTempPath(), "NeXroll");
        }

        return Path.Combine(baseDir, "intro_cache");
    }

    /// <inheritdoc />
    public string Name => "NeXroll Intros";

    /// <summary>
    /// Initializes a new instance of the <see cref="NexrollIntroProvider"/> class.
    /// </summary>
    public NexrollIntroProvider(
        ILogger<NexrollIntroProvider> logger,
        ILibraryManager libraryManager,
        IFileSystem fileSystem)
    {
        _logger = logger;
        _libraryManager = libraryManager;
        _fileSystem = fileSystem;
    }

    /// <summary>
    /// Build an HttpRequestMessage with the standard NeXroll plugin headers
    /// (API key + server identity).
    /// </summary>
    private static HttpRequestMessage BuildRequest(HttpMethod method, string url, PluginConfiguration config)
    {
        var request = new HttpRequestMessage(method, url);

        // API key authentication
        if (!string.IsNullOrWhiteSpace(config.ApiKey))
        {
            request.Headers.Add("X-Api-Key", config.ApiKey.Trim());
        }

        // Server identity headers for plugin tracking
        request.Headers.Add("X-Plugin-Server-Type", "Jellyfin");

        // Try to get Jellyfin server name/version from the running instance
        try
        {
            var serverName = System.Environment.MachineName;
            request.Headers.Add("X-Plugin-Server-Name", serverName);
        }
        catch { /* ignore */ }

        request.Headers.Add("X-Plugin-Server-Version", typeof(NexrollIntroProvider).Assembly.GetName().Version?.ToString() ?? "1.0.0");

        return request;
    }

    /// <inheritdoc />
    public async Task<IEnumerable<IntroInfo>> GetIntros(BaseItem item, User user)
    {
        var config = Plugin.Instance?.Configuration;
        if (config is null || string.IsNullOrWhiteSpace(config.NexrollUrl))
        {
            return Enumerable.Empty<IntroInfo>();
        }

        // Determine media type and check if enabled
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
            // Not a supported media type for intros
            return Enumerable.Empty<IntroInfo>();
        }

        try
        {
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
                _logger.LogDebug("NeXroll returned no intros for {MediaType} '{Name}'", mediaType, item.Name);
                return Enumerable.Empty<IntroInfo>();
            }

            var intros = new List<IntroInfo>();
            var items = response.Items;
            int maxCount;
            if (response.Exact)
            {
                // NeXroll 2.2.1 and later has already chosen what plays and in
                // what order: one preroll from a random category, every block of
                // a sequence. Max Intros used to be the only way to get one
                // preroll from a random category, and it cut sequences short.
                maxCount = items.Count;
            }
            else
            {
                // Older NeXroll sends a whole category and leaves the count here.
                maxCount = config.MaxIntros > 0 ? config.MaxIntros : items.Count;
                if (string.Equals(response.Mode, "shuffle", StringComparison.OrdinalIgnoreCase))
                {
                    items = items.OrderBy(_ => Random.Shared.Next()).ToList();
                }
            }

            foreach (var intro in items.Take(maxCount))
            {
                var introInfo = await ResolveIntroInfo(intro, config).ConfigureAwait(false);
                if (introInfo is not null)
                    intros.Add(introInfo);
            }

            _logger.LogInformation(
                "NeXroll: Injecting {Count} intro(s) before {MediaType} '{Name}' (mode={Mode})",
                intros.Count, mediaType, item.Name, response.Mode);

            return intros;
        }
        catch (TaskCanceledException)
        {
            _logger.LogWarning("NeXroll server request timed out ({Timeout}s)", config.TimeoutSeconds);
            return Enumerable.Empty<IntroInfo>();
        }
        catch (HttpRequestException ex)
        {
            _logger.LogWarning(ex, "Failed to reach NeXroll server at {Url}", config.NexrollUrl);
            return Enumerable.Empty<IntroInfo>();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Unexpected error fetching intros from NeXroll");
            return Enumerable.Empty<IntroInfo>();
        }
    }

    /// <summary>
    /// Resolve a preroll item to an IntroInfo that Jellyfin can actually play.
    /// Downloads the file to a local cache if needed, then ensures it exists
    /// as a Video item in Jellyfin's database (required by ResolveIntro).
    /// Returns IntroInfo with ItemId for direct database lookup.
    /// </summary>
    private async Task<IntroInfo?> ResolveIntroInfo(NexrollIntroItem intro, PluginConfiguration config)
    {
        // Get a local file path for the intro (download if necessary)
        var localPath = await EnsureLocalFile(intro, config).ConfigureAwait(false);
        if (string.IsNullOrWhiteSpace(localPath))
            return null;

        // Ensure the video is registered in Jellyfin's database
        var videoId = EnsureVideoInDatabase(localPath, intro.Name);
        if (videoId is null)
        {
            // Fall back to path-based IntroInfo (may not work but worth trying)
            _logger.LogWarning("NeXroll: Could not register '{Name}' in DB, falling back to path", intro.Name);
            return new IntroInfo { Path = localPath };
        }

        _logger.LogDebug("NeXroll: Resolved '{Name}' as ItemId {Id}", intro.Name, videoId.Value);
        return new IntroInfo { ItemId = videoId.Value };
    }

    /// <summary>
    /// Ensure the intro file exists on the local filesystem. Downloads from
    /// the NeXroll streaming endpoint if the file is remote or UNC.
    /// </summary>
    private async Task<string?> EnsureLocalFile(NexrollIntroItem intro, PluginConfiguration config)
    {
        // 1) Try the original (translated) file path — works for LOCAL drives only
        var translated = TranslatePath(intro.Path, config);
        if (!string.IsNullOrWhiteSpace(translated)
            && !translated.StartsWith(@"\\", StringComparison.Ordinal)
            && File.Exists(translated))
        {
            return translated;
        }

        // 2) Fall back to streaming download to local cache
        if (string.IsNullOrWhiteSpace(intro.StreamUrl))
        {
            _logger.LogDebug("NeXroll: No local file and no StreamUrl for '{Name}'", intro.Name);
            return null;
        }

        var cacheDir = GetCacheDir();
        var ext = Path.GetExtension(intro.Path);
        if (string.IsNullOrEmpty(ext)) ext = ".mp4";
        var key = SHA256Hash(intro.Path);
        // NeXroll 2.2.8 and later sends each file's version (its size and
        // modified time), and each version gets its own cache file. Named by
        // path alone, a file NeXroll rewrites under the same name, such as a
        // regenerated Coming Soon list, kept playing its first download. A new
        // name also gives Jellyfin a fresh item, so its stored size is right.
        var cached = Path.Combine(cacheDir, string.IsNullOrWhiteSpace(intro.Version)
            ? $"{key}{ext}"
            : $"{key}-{SHA256Hash(intro.Version)[..12]}{ext}");

        try
        {
            Directory.CreateDirectory(cacheDir);

            if (File.Exists(cached))
            {
                _logger.LogDebug("NeXroll: Using cached intro '{Name}' at {Path}", intro.Name, cached);
                RemoveOtherCopies(cacheDir, key, cached);
                return cached;
            }

            _logger.LogInformation("NeXroll: Downloading intro '{Name}' to cache", intro.Name);
            using var dlCts = new CancellationTokenSource(TimeSpan.FromSeconds(60));
            using var dlResp = await _httpClient.GetAsync(intro.StreamUrl, HttpCompletionOption.ResponseHeadersRead, dlCts.Token).ConfigureAwait(false);
            dlResp.EnsureSuccessStatusCode();

            var tmpPath = cached + ".tmp";
            await using (var fs = new FileStream(tmpPath, FileMode.Create, FileAccess.Write, FileShare.None))
            {
                await dlResp.Content.CopyToAsync(fs, dlCts.Token).ConfigureAwait(false);
            }

            File.Move(tmpPath, cached, overwrite: true);
            _logger.LogInformation("NeXroll: Cached intro '{Name}' ({Size:N0} bytes) at {Path}",
                intro.Name, new FileInfo(cached).Length, cached);
            RemoveOtherCopies(cacheDir, key, cached);
            return cached;
        }
        catch (Exception ex)
        {
            // An earlier version still beats playing nothing.
            var fallback = NewestCopy(cacheDir, key);
            _logger.LogWarning(ex, "NeXroll: Failed to download intro '{Name}' from streaming endpoint{Fallback}",
                intro.Name, fallback is null ? string.Empty : "; playing the copy cached earlier");
            return fallback;
        }
    }

    /// <summary>
    /// Delete this intro's cached copies other than <paramref name="keep"/>:
    /// earlier versions, and the copy older plugins named by path alone. A copy
    /// that is playing can't be deleted on Windows; it goes on a later play.
    /// </summary>
    private void RemoveOtherCopies(string cacheDir, string key, string keep)
    {
        try
        {
            foreach (var file in Directory.EnumerateFiles(cacheDir, key + "*"))
            {
                if (string.Equals(file, keep, StringComparison.OrdinalIgnoreCase)
                    || file.EndsWith(".tmp", StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                try
                {
                    File.Delete(file);
                    _logger.LogDebug("NeXroll: Removed outdated cached intro {Path}", file);
                }
                catch (IOException)
                {
                }
                catch (UnauthorizedAccessException)
                {
                }
            }
        }
        catch (Exception ex)
        {
            _logger.LogDebug(ex, "NeXroll: Could not tidy the intro cache");
        }
    }

    /// <summary>The most recently written cached copy of an intro, or null.</summary>
    private static string? NewestCopy(string cacheDir, string key)
    {
        try
        {
            return Directory.EnumerateFiles(cacheDir, key + "*")
                .Where(file => !file.EndsWith(".tmp", StringComparison.OrdinalIgnoreCase))
                .OrderByDescending(File.GetLastWriteTimeUtc)
                .FirstOrDefault();
        }
        catch
        {
            return null;
        }
    }

    /// <summary>
    /// Ensure a video file at the given local path is registered in Jellyfin's
    /// item database.  Jellyfin's ResolveIntro requires the Video to exist in
    /// the DB when looking up by ItemId.  We use ResolvePath to create the
    /// Video object (which computes its deterministic GUID), then check if it
    /// already exists in the DB.  If not, we save it.
    /// </summary>
    private Guid? EnsureVideoInDatabase(string localPath, string introName)
    {
        try
        {
            var fileInfo = _fileSystem.GetFileSystemInfo(localPath);
            var resolved = _libraryManager.ResolvePath(fileInfo);

            if (resolved is not Video video)
            {
                _logger.LogWarning("NeXroll: ResolvePath did not return a Video for '{Path}'", localPath);
                return null;
            }

            // Check if it already exists in the database
            var existing = _libraryManager.GetItemById(video.Id);
            var file = new FileInfo(localPath);
            if (existing is Video)
            {
                if (!ChangedSinceRegistered(existing, file))
                {
                    _logger.LogDebug("NeXroll: Video '{Name}' already in DB with Id {Id}", introName, video.Id);
                    return video.Id;
                }

                // Jellyfin keeps an intro's length and size from when it first
                // played it. A file rewritten at the same path, such as a
                // regenerated Coming Soon list read straight from NeXroll's
                // folder, kept the old ones, so the player showed the old
                // length. Registered afresh, Jellyfin reads the file again.
                _logger.LogInformation("NeXroll: Intro '{Name}' changed on disk; registering it again", introName);
                _libraryManager.DeleteItem(existing, new DeleteOptions { DeleteFileLocation = false });
            }

            // Not in DB yet — save it
            video.Name = introName;
            video.DateModified = file.LastWriteTimeUtc;
            _libraryManager.CreateItem(video, null);
            _logger.LogInformation("NeXroll: Registered intro '{Name}' in Jellyfin DB with Id {Id}", introName, video.Id);

            return video.Id;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "NeXroll: Failed to register video in DB for '{Path}'", localPath);
            return null;
        }
    }

    /// <summary>
    /// Whether the file was rewritten after Jellyfin registered it: written
    /// later than the record says, or a different size than Jellyfin measured.
    /// Records are compared as UTC (Jellyfin stores UTC, often without saying
    /// so); a second of slack covers file systems with coarse timestamps.
    /// </summary>
    private static bool ChangedSinceRegistered(BaseItem existing, FileInfo file)
    {
        if (!file.Exists)
        {
            return false;
        }

        if (existing.Size is long size && size > 0 && size != file.Length)
        {
            return true;
        }

        var recorded = existing.DateModified.Kind == DateTimeKind.Local
            ? existing.DateModified.ToUniversalTime()
            : DateTime.SpecifyKind(existing.DateModified, DateTimeKind.Utc);
        return file.LastWriteTimeUtc > recorded.AddSeconds(1);
    }

    /// <summary>
    /// Translate a NeXroll local path to a Jellyfin-accessible path using
    /// the configured prefix replacement.
    /// </summary>
    private static string TranslatePath(string path, PluginConfiguration config)
    {
        if (string.IsNullOrWhiteSpace(path)) return path;

        if (!string.IsNullOrWhiteSpace(config.PathPrefixFrom)
            && !string.IsNullOrWhiteSpace(config.PathPrefixTo))
        {
            var from = config.PathPrefixFrom.TrimEnd('/', '\\');
            var to = config.PathPrefixTo.TrimEnd('/', '\\');

            // Normalise separators for comparison
            var normPath = path.Replace('\\', '/');
            var normFrom = from.Replace('\\', '/');

            if (normPath.StartsWith(normFrom, StringComparison.OrdinalIgnoreCase))
            {
                var rest = normPath[normFrom.Length..];
                // Use the separator style of the target prefix
                if (to.Contains('\\'))
                    rest = rest.Replace('/', '\\');
                else
                    rest = rest.Replace('\\', '/');

                return to + rest;
            }
        }

        return path;
    }

    // --- DTO for the /plugin/intros response ---

    private sealed class NexrollIntroResponse
    {
        public List<NexrollIntroItem> Items { get; set; } = new();
        public int TotalRecordCount { get; set; }
        public string Mode { get; set; } = "shuffle";

        /// <summary>True when NeXroll has picked exactly what to play (2.2.1+).</summary>
        public bool Exact { get; set; }
    }

    private sealed class NexrollIntroItem
    {
        public string Path { get; set; } = string.Empty;
        public string Name { get; set; } = string.Empty;
        public string StreamUrl { get; set; } = string.Empty;

        /// <summary>Changes whenever the file is rewritten (NeXroll 2.2.8+); empty from older NeXroll.</summary>
        public string Version { get; set; } = string.Empty;
    }

    private static string SHA256Hash(string input)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(input));
        return Convert.ToHexString(bytes).ToLowerInvariant();
    }
}
