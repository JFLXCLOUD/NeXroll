using MediaBrowser.Model.Plugins;

namespace NeXroll.Jellyfin;

/// <summary>
/// Holds user-configurable settings for the NeXroll Intros plugin.
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
    /// Used to translate paths so Jellyfin can find the files.
    /// Example: "/data/prerolls"
    /// </summary>
    public string PathPrefixFrom { get; set; } = string.Empty;

    /// <summary>
    /// Replacement path prefix that Jellyfin can access.
    /// Example: "/mnt/media/prerolls"
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
    /// 0 = unlimited (use all returned by NeXroll).
    /// </summary>
    public int MaxIntros { get; set; } = 0;

    /// <summary>
    /// Request timeout in seconds when calling the NeXroll server.
    /// </summary>
    public int TimeoutSeconds { get; set; } = 5;
}
