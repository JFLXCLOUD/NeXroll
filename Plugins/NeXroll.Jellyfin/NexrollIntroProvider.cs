using System.Net.Http.Json;
using Jellyfin.Data.Entities;
using MediaBrowser.Controller.Entities;
using MediaBrowser.Controller.Entities.Movies;
using MediaBrowser.Controller.Entities.TV;
using MediaBrowser.Controller.Library;
using MediaBrowser.Model.Dto;
using Microsoft.Extensions.Logging;

namespace NeXroll.Jellyfin;

/// <summary>
/// Jellyfin intro provider that fetches the currently-active preroll
/// paths from a NeXroll server and returns them as <see cref="IntroInfo"/>
/// items for playback injection.
/// </summary>
public class NexrollIntroProvider : IIntroProvider
{
    private readonly ILogger<NexrollIntroProvider> _logger;
    private static readonly HttpClient _httpClient = new();

    public string Name => "NeXroll Intros";

    public NexrollIntroProvider(ILogger<NexrollIntroProvider> logger)
    {
        _logger = logger;
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

            var response = await _httpClient.GetFromJsonAsync<NexrollIntroResponse>(url, cts.Token)
                .ConfigureAwait(false);

            if (response?.Items is null || response.Items.Count == 0)
            {
                _logger.LogDebug("NeXroll returned no intros for {MediaType} '{Name}'", mediaType, item.Name);
                return Enumerable.Empty<IntroInfo>();
            }

            var intros = new List<IntroInfo>();
            var maxCount = config.MaxIntros > 0 ? config.MaxIntros : response.Items.Count;

            // If mode is "shuffle", randomise the order; otherwise keep sequential
            var items = response.Items;
            if (string.Equals(response.Mode, "shuffle", StringComparison.OrdinalIgnoreCase))
            {
                items = items.OrderBy(_ => Random.Shared.Next()).ToList();
            }

            foreach (var intro in items.Take(maxCount))
            {
                var path = TranslatePath(intro.Path, config);
                if (string.IsNullOrWhiteSpace(path)) continue;

                intros.Add(new IntroInfo { Path = path });
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
    }

    private sealed class NexrollIntroItem
    {
        public string Path { get; set; } = string.Empty;
        public string Name { get; set; } = string.Empty;
    }
}
