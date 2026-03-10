using MediaBrowser.Common.Configuration;
using MediaBrowser.Common.Plugins;
using MediaBrowser.Model.Plugins;
using MediaBrowser.Model.Serialization;

namespace NeXroll.Jellyfin;

/// <summary>
/// Main plugin class for NeXroll Intros.
/// Registers the plugin with Jellyfin and exposes configuration.
/// </summary>
public class Plugin : BasePlugin<PluginConfiguration>, IHasWebPages
{
    /// <summary>Plugin name shown in the Jellyfin dashboard.</summary>
    public override string Name => "NeXroll Intros";

    /// <summary>Unique plugin identifier.</summary>
    public override Guid Id => new("a1b2c3d4-e5f6-7890-abcd-ae0c01100001");

    /// <summary>Short description for the plugin catalog.</summary>
    public override string Description =>
        "Injects preroll intros from a NeXroll server before movies and episodes.";

    /// <summary>Current singleton instance (set by the constructor).</summary>
    public static Plugin? Instance { get; private set; }

    public Plugin(
        IApplicationPaths applicationPaths,
        IXmlSerializer xmlSerializer)
        : base(applicationPaths, xmlSerializer)
    {
        Instance = this;
    }

    /// <inheritdoc />
    public IEnumerable<PluginPageInfo> GetPages()
    {
        return new[]
        {
            new PluginPageInfo
            {
                Name = Name,
                EmbeddedResourcePath = $"{GetType().Namespace}.Configuration.configPage.html"
            }
        };
    }
}
