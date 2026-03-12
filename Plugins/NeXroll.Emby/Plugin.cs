using MediaBrowser.Common.Configuration;
using MediaBrowser.Common.Plugins;
using MediaBrowser.Model.Plugins;
using MediaBrowser.Model.Serialization;

namespace NeXroll.Emby;

/// <summary>
/// Main plugin class for NeXroll Intros (Emby variant).
/// </summary>
public class Plugin : BasePlugin<PluginConfiguration>, IHasWebPages
{
    public override string Name => "NeXroll Intros";

    public override Guid Id => new("a1b2c3d4-e5f6-7890-abcd-ae0c01200002");

    public override string Description =>
        "Injects preroll intros from a NeXroll server before movies and episodes.";

    public static Plugin? Instance { get; private set; }

    public Plugin(
        IApplicationPaths applicationPaths,
        IXmlSerializer xmlSerializer)
        : base(applicationPaths, xmlSerializer)
    {
        Instance = this;
    }

    public IEnumerable<PluginPageInfo> GetPages()
    {
        return new[]
        {
            new PluginPageInfo
            {
                Name = Name,
                EmbeddedResourcePath = $"{GetType().Namespace}.Configuration.configPage.html"
            },
            new PluginPageInfo
            {
                Name = Name + ".js",
                EmbeddedResourcePath = $"{GetType().Namespace}.Configuration.configPage.js"
            }
        };
    }
}
