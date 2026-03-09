using MediaBrowser.Model.Plugins;

namespace NeXroll.Emby;

/// <summary>
/// Holds user-configurable settings for the NeXroll Intros Emby plugin.
/// </summary>
public class PluginConfiguration : BasePluginConfiguration
{
    /// <summary>
    /// Base URL of the NeXroll server, e.g. "http://192.168.1.50:9393".
    /// </summary>
    public string NexrollUrl { get; set; } = string.Empty;

    /// <summary>
    /// Optional API key for authenticating with the NeXroll server (future use).
    /// </summary>
    public string ApiKey { get; set; } = string.Empty;

    /// <summary>
    /// Path prefix as seen by NeXroll (the local/container path).
    /// Used to translate paths so Emby can find the files.
    /// </summary>
    public string PathPrefixFrom { get; set; } = string.Empty;

    /// <summary>
    /// Replacement path prefix that Emby can access.
    /// </summary>
    public string PathPrefixTo { get; set; } = string.Empty;

    /// <summary>
    /// Whether to inject intros before movies.
    /// </summary>
    public bool EnableForMovies { get; set; } = true;

    /// <summary>
    /// Whether to inject intros before episodes.
    /// </summary>
    public bool EnableForEpisodes { get; set; } = true;

    /// <summary>
    /// Maximum number of intros to inject per playback session.
    /// 0 = unlimited.
    /// </summary>
    public int MaxIntros { get; set; } = 0;

    /// <summary>
    /// Request timeout in seconds.
    /// </summary>
    public int TimeoutSeconds { get; set; } = 5;
}
