import React from 'react';
import {
  AlertTriangle, Check, Film, Gauge, Image, Layers, Loader2, Music,
  Play, Sparkles, Trash2, Upload, Video, X
} from 'lucide-react';
import { prepareDynamicPrerollOptions, startDynamicPrerollPreview, startThemeBackdropPreview } from '../utils/dynamicPrerollMotion';

const RESOLUTIONS = [
  { id: '720', label: '720p', size: '1280 x 720', copy: 'Fast previews and smaller files.' },
  { id: '1080', label: '1080p', size: '1920 x 1080', copy: 'Best balance for most servers.' },
  { id: '2160', label: '4K', size: '3840 x 2160', copy: 'Maximum detail for large screens.' },
];

const QUALITY_PROFILES = [
  { id: 'draft', label: 'Draft', copy: 'Fastest render', crf: 'CRF 24' },
  { id: 'balanced', label: 'Balanced', copy: 'Smaller delivery file', crf: 'CRF 20' },
  { id: 'high', label: 'High', copy: 'Premium playback', crf: 'CRF 15' },
  { id: 'master', label: 'Master', copy: 'Archival quality', crf: 'CRF 12' },
];

const FONT_SIZES = [
  { value: 0.85, label: 'Compact', detail: '85%' },
  { value: 1, label: 'Standard', detail: '100%' },
  { value: 1.15, label: 'Large', detail: '115%' },
  { value: 1.3, label: 'Extra large', detail: '130%' },
  { value: 1.45, label: 'Huge', detail: '145%' },
  { value: 1.6, label: 'Maximum', detail: '160%' },
];

// Keyed by the Render confidence check label, so the blocked-render line always
// names the step the checklist is actually flagging.
const BLOCK_REASONS = {
  'FFmpeg encoder': 'Install FFmpeg',
  'Output folder': 'Choose a NeX-Up storage folder',
  'Media source': 'Connect Radarr or Sonarr',
  'Titles to list': 'Raise the maximum item count above zero',
  'Custom soundtrack': 'Upload a soundtrack or switch to Default audio',
  'Server name': 'Enter a server name',
  Headline: 'Enter a headline for the custom message',
  'Link to encode': 'Enter the link the QR code should encode',
};

const COPY = {
  en: { coming: 'COMING SOON', to: 'to', feature: 'FEATURE PRESENTATION', now: 'NOW SHOWING', comingTo: 'COMING SOON TO', available: 'Available Now!' },
  fr: { coming: 'PROCHAINEMENT', to: 'sur', feature: 'LONG M\u00c9TRAGE', now: '\u00c0 L\'AFFICHE', comingTo: 'PROCHAINEMENT SUR', available: 'Maintenant disponible!' },
  es: { coming: 'PR\u00d3XIMAMENTE', to: 'en', feature: 'FUNCI\u00d3N PRINCIPAL', now: 'EN CARTELERA', comingTo: 'PR\u00d3XIMAMENTE EN', available: '\u00a1Disponible!' },
  de: { coming: 'DEMN\u00c4CHST', to: 'auf', feature: 'HAUPTFILM', now: 'JETZT IM PROGRAMM', comingTo: 'DEMN\u00c4CHST AUF', available: 'Jetzt verf\u00fcgbar!' },
};

const normalizeColor = (value, fallback) => String(value || fallback).replace(/^0x/i, '#');
const captureRgba = (value, alpha, fallback) => {
  const normalized = normalizeColor(value, fallback).trim();
  const shorthand = normalized.match(/^#([0-9a-f]{3})$/i);
  const full = normalized.match(/^#([0-9a-f]{6})$/i);
  const hex = shorthand
    ? shorthand[1].split('').map(character => character + character).join('')
    : full?.[1];

  if (!hex) return normalizeColor(fallback, '#000000');
  const numeric = Number.parseInt(hex, 16);
  return `rgba(${(numeric >> 16) & 255}, ${(numeric >> 8) & 255}, ${numeric & 255}, ${alpha})`;
};
const outputFor = settings => RESOLUTIONS.find(item => item.id === String(settings.resolution || '1080')) || RESOLUTIONS[1];
const profileFor = settings => QUALITY_PROFILES.find(item => item.id === settings.renderQuality) || QUALITY_PROFILES[1];
const themeLabel = (id, theme = {}) => theme.label || id.replaceAll('_', ' ').replace(/\b\w/g, character => character.toUpperCase());

function StudioBadge({ tone = '', children }) {
  return <span className={`nx-gen-badge ${tone}`.trim()}>{children}</span>;
}

function StudioSwitch({ checked, onChange, label }) {
  return (
    <button type="button" className={`nx-gen-switch${checked ? ' on' : ''}`} role="switch" aria-checked={checked} aria-label={label} onClick={() => onChange(!checked)}>
      <i />
    </button>
  );
}

function SectionHeader({ step, title, copy, icon: Icon }) {
  return (
    <header className="nx-gen-section-head">
      <span className="nx-gen-step">{step}</span>
      <i><Icon size={16} /></i>
      <div><h3>{title}</h3><p>{copy}</p></div>
    </header>
  );
}

function AssetControl({ icon: Icon, title, copy, filename, accept, onUpload, onRemove }) {
  return (
    <div className={`nx-gen-asset${filename ? ' ready' : ''}`}>
      <i><Icon size={18} /></i>
      <div><strong>{title}</strong><span>{filename || copy}</span></div>
      <label className="nx-gen-btn subtle"><Upload size={13} /> {filename ? 'Replace' : 'Browse'}<input type="file" accept={accept} onChange={event => { const file = event.target.files?.[0]; if (file) onUpload(file); event.target.value = ''; }} /></label>
      {filename && <button type="button" className="nx-gen-icon-btn danger" title={`Remove ${title}`} onClick={onRemove}><X size={14} /></button>}
    </div>
  );
}

function RenderControls({ settings, update, defaultQuality }) {
  const quality = settings.renderQuality || defaultQuality;
  return (
    <section className="nx-gen-card nx-gen-output-card">
      <SectionHeader step="04" icon={Gauge} title="Render output" copy="Choose the actual dimensions, motion cadence, and encoder quality for the MP4." />
      <div className="nx-gen-card-body">
        <div className="nx-gen-field-label">Resolution</div>
        <div className="nx-gen-resolution-grid">
          {RESOLUTIONS.map(item => <button type="button" key={item.id} className={String(settings.resolution || '1080') === item.id ? 'active' : ''} onClick={() => update({ resolution: item.id })}><span>{item.label}</span><strong>{item.size}</strong><small>{item.copy}</small>{String(settings.resolution || '1080') === item.id && <Check size={14} />}</button>)}
        </div>
        <div className="nx-gen-output-row">
          <label><span>Frame rate</span><select value={settings.frameRate || 30} onChange={event => update({ frameRate: Number(event.target.value) })}><option value={24}>24 fps / Cinematic</option><option value={30}>30 fps / Standard</option><option value={60}>60 fps / Smooth</option></select></label>
          <div><span className="nx-gen-field-label">Encoding profile</span><div className="nx-gen-quality-grid">{QUALITY_PROFILES.map(item => <button type="button" key={item.id} className={quality === item.id ? 'active' : ''} onClick={() => update({ renderQuality: item.id })}><strong>{item.label}</strong><span>{item.copy}</span><small>{item.crf}</small></button>)}</div></div>
        </div>
        <div className="nx-gen-quality-note"><Sparkles size={14} /><span>All profiles use H.264 High Profile, web-optimized MP4 output, Lanczos scaling, and AAC when a soundtrack is selected. High is recommended for finished prerolls.</span></div>
      </div>
    </section>
  );
}

function DynamicCanvas({ settings, selectedTemplate, selectedTheme, previewRef, logoUrl, qrUrl }) {
  const template = settings.template || 'coming_soon';
  const canvasRef = React.useRef(null);

  React.useEffect(() => {
    let disposed = false;
    let stopPreview = () => {};
    prepareDynamicPrerollOptions({
      settings: { ...settings },
      theme: { ...selectedTheme },
      templateName: selectedTemplate?.name || 'Dynamic preroll',
      logoUrl,
      qrUrl,
    }).then(options => {
      if (!disposed) stopPreview = startDynamicPrerollPreview(canvasRef.current, options);
    });
    return () => {
      disposed = true;
      stopPreview();
    };
  }, [settings, selectedTemplate?.name, selectedTheme, logoUrl, qrUrl]);

  const assignPreviewRef = node => {
    canvasRef.current = node;
    if (previewRef) previewRef.current = node;
  };

  return (
    <canvas
      ref={assignPreviewRef}
      className={`nx-gen-canvas nx-gen-motion-canvas nx-gen-canvas-${template}`}
      width="1280"
      height="720"
      aria-label={`Animated ${selectedTemplate?.name || 'dynamic preroll'} preview`}
    />
  );
}

function ComingCanvas({ settings, logoUrl, themePalette, qrUrl }) {
  const text = COPY[settings.language] || COPY.en;
  const hasLogo = Boolean(settings.customLogoFilename);
  const sampleCount = Math.min(Number(settings.maxItems || 8), settings.layout === 'list' ? 6 : 5);
  // A chosen theme supplies the palette the renderer will actually use, so the
  // preview has to read from it rather than the manual pickers it overrides.
  const background = normalizeColor(themePalette?.bg ?? settings.bgColor, '#141428');
  const primary = normalizeColor(themePalette?.primary ?? settings.textColor, '#ffffff');
  const accent = normalizeColor(themePalette?.secondary ?? settings.accentColor, '#00d4ff');
  const backdropRef = React.useRef(null);

  // Draw the theme's own backdrop behind the list, using the same renderer the
  // dynamic templates preview with, so both generators read as one family.
  // Only themed mode animates; hand-picked colours stay a flat wash because
  // that is what the renderer produces for them.
  React.useEffect(() => {
    if (!themePalette || !backdropRef.current) return undefined;
    return startThemeBackdropPreview(backdropRef.current, themePalette);
  }, [themePalette]);

  return (
    <div className={`nx-gen-canvas nx-gen-coming-canvas layout-${settings.layout}`} style={{
      '--gen-bg': background,
      '--gen-primary': primary,
      '--gen-primary-78': captureRgba(primary, 0.78, '#ffffff'),
      '--gen-accent': accent,
      '--gen-accent-13': captureRgba(accent, 0.13, '#00d4ff'),
      '--gen-accent-23': captureRgba(accent, 0.23, '#00d4ff'),
      '--gen-accent-42': captureRgba(accent, 0.42, '#00d4ff'),
      '--gen-accent-65': captureRgba(accent, 0.65, '#00d4ff'),
      '--gen-font-scale': Number(settings.fontScale || 1),
      '--gen-title': normalizeColor(settings.titleColor, primary),
      '--gen-date': normalizeColor(settings.dateColor, accent),
      '--gen-available': normalizeColor(settings.availableColor, '#28a745'),
    }}>
      {themePalette && <canvas ref={backdropRef} className="nx-gen-coming-backdrop" width="1280" height="720" aria-hidden="true" />}
      <div className="nx-gen-coming-vignette" />
      {hasLogo && settings.logoMode === 'watermark' && <img className="nx-gen-watermark" src={logoUrl} alt="" />}
      <div className="nx-gen-coming-head">
        <div><span>{hasLogo && settings.logoMode !== 'watermark' ? text.comingTo : text.coming}</span>{(!hasLogo || settings.logoMode === 'watermark') && <small>{text.to} {settings.serverName || 'Your Server'}</small>}</div>
        {hasLogo && settings.logoMode !== 'watermark' && <img className={settings.logoMode === 'below' ? 'below' : ''} src={logoUrl} alt="Custom server logo" />}
      </div>
      <i className="nx-gen-coming-rule" />
      {settings.layout === 'list' ? <div className="nx-gen-sample-list">{Array.from({ length: sampleCount }, (_, index) => <div key={index}><span><i /> {index === 0 ? 'A New Adventure' : `Upcoming title ${index + 1}`}</span><b className={index === 0 ? 'is-available' : ''}>{index === 0 ? text.available : `MAR ${10 + index * 3}`}</b></div>)}</div> : <div className="nx-gen-poster-grid">{Array.from({ length: sampleCount }, (_, index) => <div key={index}><i><Film size={18} /></i><span className={index === 0 ? 'is-available' : ''}>{index === 0 ? text.available : `MAR ${10 + index * 3}`}</span></div>)}</div>}
      {qrUrl && <img className="nx-gen-coming-qr" src={qrUrl} alt="QR code preview" />}
    </div>
  );
}

// "Both" generates a grid video and a list video, so the stage shows both
// rather than silently previewing only the grid.
function ComingSoonStage(props) {
  const layout = props.settings.layout;
  if (layout !== 'both') return <ComingCanvas {...props} />;
  return (
    <div className="nx-gen-stage-stack">
      {['grid', 'list'].map(single => (
        <figure key={single}>
          <figcaption>{single === 'grid' ? 'Poster grid' : 'Text list'}</figcaption>
          <ComingCanvas {...props} settings={{ ...props.settings, layout: single }} />
        </figure>
      ))}
    </div>
  );
}

function RecentOutputs({ mode, items, onPreview, onDelete }) {
  if (!items.length) return null;
  return (
    <section className="nx-gen-card nx-gen-recent">
      <header className="nx-gen-recent-head"><div><h3>Recent generated {mode === 'dynamic' ? 'prerolls' : 'lists'}</h3><p>Saved to the NeXroll library and ready for sequences.</p></div><StudioBadge>{items.length} files</StudioBadge></header>
      <div className="nx-gen-recent-grid">{items.slice(0, 6).map((item, index) => <article key={item.filename || index}><button type="button" className={`nx-gen-output-art art-${index % 3}`} onClick={() => onPreview(item)}><Play size={18} /><span>{mode === 'dynamic' ? 'SERVER IDENT' : 'COMING SOON'}</span></button><div><strong>{item.name || item.filename || 'Generated video'}</strong><span>{item.size_bytes ? `${(Number(item.size_bytes) / 1048576).toFixed(1)} MB` : 'MP4 video'}</span><button type="button" title="Delete generated video" onClick={() => onDelete(item.filename)}><Trash2 size={14} /></button></div></article>)}</div>
    </section>
  );
}

export default function NeXUpGeneratorStudio(props) {
  const {
    settings, generatorTab, setGeneratorTab,
    dynamicSettings, setDynamicSettings, templates, colorThemes, ffmpegAvailable,
    dynamicGenerating, generatedPrerolls, onGenerateDynamic, onPreviewDynamic, onDeleteDynamic,
    previewRef, dynamicLogoUrl, dynamicQrUrl, comingLogoUrl, comingQrUrl, onUploadAsset, onRemoveAsset,
    comingSettings, setComingSettings, comingGenerating, generatedComingLists,
    onGenerateComing, onPreviewComing, onDeleteComing, onNavigate, onSaveDynamic, onSaveComing,
  } = props;
  const connected = Boolean(settings.radarr_connected || settings.sonarr_connected);
  const templateOptions = templates.length ? templates : [
    { id: 'coming_soon', name: 'Coming Soon', description: 'Cinematic glow and a dramatic server reveal.' },
    { id: 'feature_presentation', name: 'Feature Presentation', description: 'Classic theatrical framing with restrained motion.' },
    { id: 'now_showing', name: 'Now Showing', description: 'Bright marquee styling with a modern finish.' },
  ];
  const selectedTemplate = templateOptions.find(item => item.id === dynamicSettings.template) || templateOptions[0];
  const themeEntries = Object.entries(colorThemes || {});
  const selectedTheme = colorThemes?.[dynamicSettings.theme] || {};
  const resolvedTitleColor = normalizeColor(dynamicSettings.titleColor, normalizeColor(selectedTheme.primary, '#00d4ff'));
  const resolvedSubjectColor = normalizeColor(dynamicSettings.subjectColor, normalizeColor(selectedTheme.secondary, '#7b2cbf'));
  // Each role falls back to the colour it inherits today, so the picker shows
  // what will actually render rather than an empty swatch.
  const comingBase = comingSettings.theme ? (colorThemes?.[comingSettings.theme] || {}) : {};
  const resolvedComingTitle = normalizeColor(comingSettings.titleColor, normalizeColor(comingBase.primary ?? comingSettings.textColor, '#ffffff'));
  const resolvedComingDate = normalizeColor(comingSettings.dateColor, normalizeColor(comingBase.secondary ?? comingSettings.accentColor, '#00d4ff'));
  const resolvedComingAvailable = normalizeColor(comingSettings.availableColor, '#28a745');
  const modeSettings = generatorTab === 'dynamic' ? dynamicSettings : comingSettings;
  const modeOutput = outputFor(modeSettings);
  const modeProfile = profileFor(modeSettings);
  const updateDynamic = updates => setDynamicSettings(previous => ({ ...previous, ...updates }));
  const updateComing = updates => setComingSettings(previous => ({ ...previous, ...updates }));
  const isGenerating = generatorTab === 'dynamic' ? dynamicGenerating : comingGenerating;
  // Custom Message and QR Code render no server name and no translated copy, so
  // they require their own field instead of the server name every other
  // template gates on.
  const isCustomText = dynamicSettings.template === 'custom_text';
  const isQrShare = dynamicSettings.template === 'qr_share';
  const usesServerName = !isCustomText && !isQrShare;
  const dynamicRequiredField = isCustomText ? 'Headline' : isQrShare ? 'Link to encode' : 'Server name';
  const dynamicRequiredReady = isCustomText
    ? Boolean(String(dynamicSettings.customHeadline || '').trim() || String(dynamicSettings.customSubtext || '').trim())
    : isQrShare
      ? Boolean(String(dynamicSettings.qrData || '').trim())
      : Boolean(dynamicSettings.server_name?.trim());
  // One list drives both the Generate button and the Render confidence panel, so
  // the panel can never read all-clear while the button stays disabled. Each
  // entry mirrors a condition the backend actually enforces: dynamic prerolls
  // draw their own canvas and need no Radarr/Sonarr connection, while a Coming
  // Soon list is built from what those sources report.
  const renderChecks = generatorTab === 'dynamic'
    ? [
      { label: 'FFmpeg encoder', ready: ffmpegAvailable },
      { label: 'Output folder', ready: Boolean(settings.storage_path) },
      { label: dynamicRequiredField, ready: dynamicRequiredReady },
      ...(dynamicSettings.audioMode === 'custom'
        ? [{ label: 'Custom soundtrack', ready: Boolean(dynamicSettings.customAudioFilename) }]
        : []),
    ]
    : [
      { label: 'FFmpeg encoder', ready: ffmpegAvailable },
      { label: 'Output folder', ready: Boolean(settings.storage_path) },
      { label: 'Media source', ready: connected },
      { label: 'Titles to list', ready: Number(comingSettings.maxItems) > 0 },
    ];
  const canGenerate = renderChecks.every(check => check.ready);
  const blockingCheck = renderChecks.find(check => !check.ready);
  const generate = () => generatorTab === 'dynamic' ? onGenerateDynamic() : onGenerateComing(comingSettings.layout);
  const previewItem = generatorTab === 'dynamic'
    ? (dynamicSettings.preroll_path ? { filename: String(dynamicSettings.preroll_path).split(/[\\/]/).pop() } : generatedPrerolls[0])
    : generatedComingLists[0];

  return (
    <div className="nx-ap-page nx-generator-studio" data-nexup-page="generator">
      <section className="nx-gen-toolbar">
        <div><span className="nx-gen-kicker"><Sparkles size={13} /> Generator Studio</span><h2>Shape the intro, then choose how cleanly it renders.</h2></div>
        <div className="nx-gen-toolbar-actions"><div className="nx-gen-mode"><button type="button" className={generatorTab === 'dynamic' ? 'active' : ''} onClick={() => setGeneratorTab('dynamic')}><Sparkles size={14} /> Dynamic</button><button type="button" className={generatorTab === 'coming-soon' ? 'active' : ''} onClick={() => setGeneratorTab('coming-soon')}><Film size={14} /> Coming Soon</button></div><div className="nx-gen-health"><StudioBadge tone={ffmpegAvailable ? 'good' : 'warn'}>{ffmpegAvailable ? 'FFmpeg ready' : 'FFmpeg required'}</StudioBadge><StudioBadge tone={settings.storage_path ? 'good' : 'warn'}>{settings.storage_path ? 'Storage ready' : 'Choose storage'}</StudioBadge></div></div>
      </section>

      {!connected && generatorTab !== 'dynamic' && <div className="nx-gen-notice"><AlertTriangle size={17} /><div><strong>Connect Radarr or Sonarr before rendering.</strong><span>A Coming Soon list is built from the upcoming titles those sources report, so one has to be connected to generate.</span></div><button type="button" className="nx-gen-btn subtle" onClick={() => onNavigate('nexup')}>Open connections</button></div>}
      {!ffmpegAvailable && <div className="nx-gen-notice danger"><AlertTriangle size={17} /><div><strong>FFmpeg is not available.</strong><span>Install FFmpeg to enable H.264 video rendering. All design controls remain editable.</span></div></div>}

      <div className="nx-gen-layout">
        <main className="nx-gen-workspace">
          {generatorTab === 'dynamic' ? <>
            <section className="nx-gen-card"><SectionHeader step="01" icon={Sparkles} title="Choose a visual direction" copy="Start with a motion identity. The preview updates immediately." /><div className="nx-gen-card-body"><div className="nx-gen-template-grid">{templateOptions.map((template, index) => <button type="button" key={template.id} className={dynamicSettings.template === template.id ? 'active' : ''} onClick={() => updateDynamic({ template: template.id })}><i className={`art art-${index % 3}`}><span>{template.name.split(' ')[0]}</span></i><div><strong>{template.name}</strong><span>{template.description}</span></div>{dynamicSettings.template === template.id && <Check size={15} />}</button>)}</div></div></section>
            <section className="nx-gen-card">
              <SectionHeader step="02" icon={Video} title="Title, timing, and tone" copy="Personalize the message while keeping the composition broadcast-safe." />
              <div className="nx-gen-card-body">
                <div className="nx-gen-fields">
                  <label><span>Name this preroll <small>(optional)</small></span><input value={dynamicSettings.name || ''} onChange={event => updateDynamic({ name: event.target.value })} placeholder="e.g. Holiday Intro" /><small>Naming it saves a distinct file you can pick individually in the Sequence Builder. Leave blank to keep overwriting the template/theme combo as before.</small></label>
                  {usesServerName && <label><span>Server name</span><input value={dynamicSettings.server_name} onChange={event => updateDynamic({ server_name: event.target.value })} placeholder="My Media Server" /></label>}
                  {isCustomText && <>
                    <label><span>Headline</span><input value={dynamicSettings.customHeadline || ''} onChange={event => updateDynamic({ customHeadline: event.target.value })} placeholder="BACK IN 5 MINUTES" maxLength={60} /></label>
                    <label><span>Supporting line <small>(optional)</small></span><input value={dynamicSettings.customSubtext || ''} onChange={event => updateDynamic({ customSubtext: event.target.value })} placeholder="Grab a refill" maxLength={80} /></label>
                  </>}
                  {isQrShare && <>
                    <label><span>Link or text to encode</span><input value={dynamicSettings.qrData || ''} onChange={event => updateDynamic({ qrData: event.target.value })} placeholder="https://example.com/watch-party" maxLength={2000} /><small>Anything scannable: a URL, a Wi-Fi guest note, a Discord invite. The preview shows the real code, so test it with your phone before rendering.</small></label>
                    <label><span>Caption <small>(optional)</small></span><input value={dynamicSettings.qrCaption || ''} onChange={event => updateDynamic({ qrCaption: event.target.value })} placeholder="SCAN TO LEARN MORE" maxLength={60} /></label>
                  </>}
                  <label><span>Duration</span><select value={dynamicSettings.duration} onChange={event => updateDynamic({ duration: Number(event.target.value) })}>{[3, 4, 5, 6, 7, 8, 10, 15, 20].map(value => <option key={value} value={value}>{value} seconds</option>)}</select></label>
                  {usesServerName && <label><span>Text language</span><select value={dynamicSettings.language} onChange={event => updateDynamic({ language: event.target.value })}><option value="en">English</option><option value="fr">French</option><option value="es">Spanish</option><option value="de">German</option></select></label>}
                  <label><span>Font size</span><select aria-label="Dynamic preroll font size" value={Number(dynamicSettings.fontScale || 1)} onChange={event => updateDynamic({ fontScale: Number(event.target.value) })}>{FONT_SIZES.map(option => <option key={option.value} value={option.value}>{option.label} / {option.detail}</option>)}</select></label>
                  <label><span>Visual theme</span><select value={dynamicSettings.theme} onChange={event => updateDynamic({ theme: event.target.value })}>{themeEntries.length ? themeEntries.map(([id, theme]) => <option key={id} value={id}>{themeLabel(id, theme)}</option>) : <option value={dynamicSettings.theme || 'midnight'}>Midnight</option>}</select></label>
                </div>
                <div className="nx-gen-color-grid two nx-gen-dynamic-colors">
                  <label><span>Heading text</span><div><input aria-label="Dynamic preroll heading text color" type="color" value={resolvedTitleColor} onChange={event => updateDynamic({ titleColor: event.target.value })} /><code>{resolvedTitleColor}</code><button type="button" onClick={() => updateDynamic({ titleColor: null })} disabled={!dynamicSettings.titleColor}>Theme</button></div></label>
                  <label><span>Server name text</span><div><input aria-label="Dynamic preroll server name text color" type="color" value={resolvedSubjectColor} onChange={event => updateDynamic({ subjectColor: event.target.value })} /><code>{resolvedSubjectColor}</code><button type="button" onClick={() => updateDynamic({ subjectColor: null })} disabled={!dynamicSettings.subjectColor}>Theme</button></div></label>
                </div>
                {themeEntries.length > 0 && (
                  <div className="nx-gen-theme-grid" aria-label="Dynamic preroll visual themes">
                    {themeEntries.map(([id, theme]) => (
                      <button type="button" key={id} className={dynamicSettings.theme === id ? 'active' : ''} onClick={() => updateDynamic({ theme: id })}>
                        <i data-effect={theme.effect || 'orbital'} style={{ '--swatch-a': normalizeColor(theme.bg, '#141428'), '--swatch-b': normalizeColor(theme.primary, '#00d4ff'), '--swatch-c': normalizeColor(theme.secondary, '#7b2cbf'), '--swatch-d': normalizeColor(theme.accent, '#ff006e') }} />
                        <span><strong>{themeLabel(id, theme)}</strong><small>{theme.description || 'Cinematic color treatment'}</small></span>
                        {theme.featured && <em>NEW</em>}
                        {dynamicSettings.theme === id && <Check size={14} />}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </section>
            <section className="nx-gen-card"><SectionHeader step="03" icon={Music} title="Brand and soundtrack" copy="Add your logo and choose whether the finished preroll uses NeXroll music, your own track, or no audio." /><div className="nx-gen-card-body"><div className="nx-gen-asset-stack"><AssetControl icon={Image} title="Custom logo" copy="PNG, JPG, or WebP - transparent PNG recommended" filename={dynamicSettings.customLogoFilename} accept=".png,.jpg,.jpeg,.webp" onUpload={file => onUploadAsset('dynamic-logo', file)} onRemove={() => onRemoveAsset('dynamic-logo')} /><div className="nx-gen-soundtrack"><span className="nx-gen-field-label">Soundtrack</span><div className="nx-gen-choice-grid">{[['default', 'Default soundtrack', 'Use the bundled cinematic music from Coming Soon.'], ['custom', 'Custom audio', dynamicSettings.customAudioFilename ? `Use ${dynamicSettings.customAudioFilename}` : 'Upload MP3, WAV, AAC, M4A, OGG, or FLAC.'], ['none', 'No audio', 'Render a video without an audio stream.']].map(([id, label, copy]) => <button type="button" key={id} className={dynamicSettings.audioMode === id ? 'active' : ''} aria-pressed={dynamicSettings.audioMode === id} onClick={() => updateDynamic({ audioMode: id })}><strong>{label}</strong><span>{copy}</span>{dynamicSettings.audioMode === id && <Check size={14} />}</button>)}</div>{dynamicSettings.audioMode === 'custom' && <div className="nx-gen-audio-upload"><AssetControl icon={Music} title="Custom soundtrack" copy="Choose an audio file; NeXroll will trim it and add smooth fades." filename={dynamicSettings.customAudioFilename} accept=".mp3,.wav,.aac,.m4a,.ogg,.flac" onUpload={file => onUploadAsset('dynamic-audio', file)} onRemove={() => onRemoveAsset('dynamic-audio')} />{!dynamicSettings.customAudioFilename && <small>Select a file before rendering with Custom audio.</small>}</div>}</div></div></div></section>
            <RenderControls settings={dynamicSettings} update={updateDynamic} defaultQuality="high" />
            <div className="nx-gen-save-row"><span>Dynamic defaults include the template, typography, soundtrack choice, timing, visual theme, and render profile.</span><button type="button" className="nx-gen-btn subtle" onClick={onSaveDynamic}>Save dynamic defaults</button></div>
          </> : <>
            <section className="nx-gen-card"><SectionHeader step="01" icon={Layers} title="Layout and content" copy="Decide how upcoming media is presented and which sources feed the list." /><div className="nx-gen-card-body"><div className="nx-gen-choice-grid">{[['grid', 'Poster grid', 'Artwork-forward with release dates.'], ['list', 'Text list', 'Compact titles and dates.'], ['both', 'Generate both', 'Create both output variations.']].map(([id, label, copy]) => <button type="button" key={id} className={comingSettings.layout === id ? 'active' : ''} onClick={() => updateComing({ layout: id })}><strong>{label}</strong><span>{copy}</span>{comingSettings.layout === id && <Check size={14} />}</button>)}</div><div className="nx-gen-fields three"><label><span>Content source</span><select value={comingSettings.source} onChange={event => updateComing({ source: event.target.value })}><option value="both">Movies and TV</option><option value="movies">Movies only</option><option value="shows">TV only</option></select></label><label><span>Text language</span><select value={comingSettings.language} onChange={event => updateComing({ language: event.target.value })}><option value="en">English</option><option value="fr">French</option><option value="es">Spanish</option><option value="de">German</option></select></label><label><span>Maximum items</span><select value={comingSettings.maxItems} onChange={event => updateComing({ maxItems: Number(event.target.value) })}>{[4, 5, 6, 7, 8, 10, 12].map(value => <option key={value} value={value}>{value} items</option>)}</select></label></div></div></section>
            <section className="nx-gen-card"><SectionHeader step="02" icon={Video} title="Presentation and branding" copy="Control timing, typography colors, music, and logo placement." /><div className="nx-gen-card-body"><div className="nx-gen-fields"><label><span>Server name</span><input value={comingSettings.serverName} onChange={event => updateComing({ serverName: event.target.value })} placeholder="Your Server" /></label><label><span>Duration</span><select value={comingSettings.duration} onChange={event => updateComing({ duration: Number(event.target.value) })}>{[5, 8, 10, 12, 15, 20, 25, 30].map(value => <option key={value} value={value}>{value} seconds</option>)}</select></label><label><span>Visual theme</span><select value={comingSettings.theme || ''} onChange={event => updateComing({ theme: event.target.value })}><option value="">Custom colors</option>{themeEntries.map(([id, theme]) => <option key={id} value={id}>{themeLabel(id, theme)}</option>)}</select><small>A theme drives the three colors below. Pick Custom colors to set them by hand.</small></label><label><span>Text size</span><select value={Number(comingSettings.fontScale || 1)} onChange={event => updateComing({ fontScale: Number(event.target.value) })}>{FONT_SIZES.map(option => <option key={option.value} value={option.value}>{option.label} / {option.detail}</option>)}</select><small>Scales the title and date text. Row spacing follows it, and the list is capped so it always fits the frame.</small></label><label><span>QR code link <small>(optional)</small></span><input value={comingSettings.qrData || ''} onChange={event => updateComing({ qrData: event.target.value })} placeholder="https://example.com/whats-on" maxLength={2000} /><small>Rendered as a scannable code in the bottom-right corner. Leave blank for none.</small></label></div><div className="nx-gen-color-grid" hidden={Boolean(comingSettings.theme)}><label><span>Background</span><div><input type="color" value={comingSettings.bgColor} onChange={event => updateComing({ bgColor: event.target.value })} /><code>{comingSettings.bgColor}</code></div></label><label><span>Text</span><div><input type="color" value={comingSettings.textColor} onChange={event => updateComing({ textColor: event.target.value })} /><code>{comingSettings.textColor}</code></div></label><label><span>Accent</span><div><input type="color" value={comingSettings.accentColor} onChange={event => updateComing({ accentColor: event.target.value })} /><code>{comingSettings.accentColor}</code></div></label></div><div className="nx-gen-color-grid nx-gen-role-colors"><label><span>Titles</span><div><input type="color" aria-label="Coming Soon title color" value={resolvedComingTitle} onChange={event => updateComing({ titleColor: event.target.value })} /><code>{resolvedComingTitle}</code><button type="button" onClick={() => updateComing({ titleColor: null })} disabled={!comingSettings.titleColor}>Inherit</button></div></label><label><span>Dates</span><div><input type="color" aria-label="Coming Soon date color" value={resolvedComingDate} onChange={event => updateComing({ dateColor: event.target.value })} /><code>{resolvedComingDate}</code><button type="button" onClick={() => updateComing({ dateColor: null })} disabled={!comingSettings.dateColor}>Inherit</button></div></label><label><span>Available now</span><div><input type="color" aria-label="Available now color" value={resolvedComingAvailable} onChange={event => updateComing({ availableColor: event.target.value })} /><code>{resolvedComingAvailable}</code><button type="button" onClick={() => updateComing({ availableColor: null })} disabled={!comingSettings.availableColor}>Default</button></div></label></div><div className="nx-gen-asset-stack"><div className="nx-gen-toggle-row"><i><Music size={18} /></i><div><strong>Background music</strong><span>Add the default cinematic bed or an uploaded audio file with automatic fades.</span></div><StudioSwitch checked={Boolean(comingSettings.includeAudio)} onChange={checked => updateComing({ includeAudio: checked })} label="Include background music" /></div><AssetControl icon={Music} title="Music file" copy={comingSettings.includeAudio ? 'Using the default cinematic track' : 'Music is currently disabled'} filename={comingSettings.customAudioFilename} accept=".mp3,.wav,.aac,.m4a,.ogg,.flac" onUpload={file => onUploadAsset('coming-audio', file)} onRemove={() => onRemoveAsset('coming-audio')} /><AssetControl icon={Image} title="Custom logo" copy="PNG, JPG, or WebP - optional" filename={comingSettings.customLogoFilename} accept=".png,.jpg,.jpeg,.webp" onUpload={file => onUploadAsset('coming-logo', file)} onRemove={() => onRemoveAsset('coming-logo')} />{comingSettings.customLogoFilename && <label className="nx-gen-inline-select"><span>Logo placement</span><select value={comingSettings.logoMode} onChange={event => updateComing({ logoMode: event.target.value })}><option value="watermark">Faded watermark</option><option value="right">Right of heading</option><option value="below">Below heading</option></select></label>}</div></div></section>
            <section className="nx-gen-card"><SectionHeader step="03" icon={Sparkles} title="Availability and automation" copy="Keep recently released titles visible and rebuild outputs after successful syncs." /><div className="nx-gen-card-body"><div className="nx-gen-automation-grid"><div className="nx-gen-option-block"><div><strong>Available Now window</strong><span>How long released items remain eligible.</span></div><label><span>Days visible</span><input type="number" min="1" max="30" value={comingSettings.availableDays} onChange={event => updateComing({ availableDays: Math.max(1, Math.min(30, Number(event.target.value) || 1)) })} /></label><label><span>Maximum items</span><input type="number" min="0" max="50" value={comingSettings.maxAvailableNow} onChange={event => updateComing({ maxAvailableNow: Math.max(0, Math.min(50, Number(event.target.value) || 0)) })} /><small>0 keeps all eligible items</small></label></div><div className="nx-gen-option-block"><div className="nx-gen-toggle-row compact"><div><strong>Auto-regenerate after sync</strong><span>Refresh generated lists when media changes.</span></div><StudioSwitch checked={Boolean(comingSettings.autoRegen)} onChange={checked => updateComing({ autoRegen: checked })} label="Auto-regenerate after sync" /></div><label><span>Automatic output</span><select value={comingSettings.autoRegenLayout} disabled={!comingSettings.autoRegen} onChange={event => updateComing({ autoRegenLayout: event.target.value })}><option value="grid">Poster grid</option><option value="list">Text list</option><option value="both">Both layouts</option></select></label></div></div></div></section>
            <RenderControls settings={comingSettings} update={updateComing} defaultQuality="balanced" />
            <div className="nx-gen-save-row"><span>Coming Soon controls save automatically; this button confirms the full current preset.</span><button type="button" className="nx-gen-btn subtle" onClick={onSaveComing}>Save Coming Soon defaults</button></div>
          </>}
        </main>

        <aside className="nx-gen-preview-rail">
          <section className="nx-gen-preview-card">
            <header><div><span>Live 16:9 canvas</span><strong>{generatorTab === 'dynamic' ? selectedTemplate?.name : 'Coming Soon list'}</strong></div><StudioBadge tone="live">LIVE</StudioBadge></header>
            <div className="nx-gen-stage">{generatorTab === 'dynamic' ? <DynamicCanvas settings={dynamicSettings} selectedTemplate={selectedTemplate} selectedTheme={selectedTheme} previewRef={previewRef} logoUrl={dynamicLogoUrl} qrUrl={dynamicQrUrl} /> : <ComingSoonStage settings={comingSettings} logoUrl={comingLogoUrl} themePalette={comingSettings.theme ? colorThemes?.[comingSettings.theme] : null} qrUrl={comingQrUrl} />}</div>
            <div className="nx-gen-render-summary"><div><span>Output</span><strong>{modeOutput.label} / {modeOutput.size}</strong></div><div><span>Motion</span><strong>{modeSettings.frameRate || 30} fps</strong></div><div><span>Quality</span><strong>{modeProfile.label} / {modeProfile.crf}</strong></div><div><span>Container</span><strong>H.264 MP4</strong></div></div>
            <div className="nx-gen-preview-actions"><button type="button" className="nx-gen-btn subtle" disabled={!previewItem} onClick={() => generatorTab === 'dynamic' ? onPreviewDynamic(previewItem) : onPreviewComing(previewItem)}><Play size={14} /> Play latest</button><button type="button" className="nx-gen-btn primary" disabled={!canGenerate || isGenerating} onClick={generate}>{isGenerating ? <Loader2 size={14} className="spin" /> : <Sparkles size={14} />} {isGenerating ? 'Rendering video...' : generatorTab === 'dynamic' ? 'Render preroll' : comingSettings.layout === 'both' ? 'Render both lists' : 'Render list'}</button></div>
            {!canGenerate && <p className="nx-gen-block-reason">{BLOCK_REASONS[blockingCheck?.label] || `Complete ${blockingCheck?.label || 'the remaining step'}`} to enable rendering.</p>}
          </section>
          <section className="nx-gen-checklist"><strong>Render confidence</strong>{renderChecks.map((check, index) => <div key={check.label} className={check.ready ? 'ready' : ''}><i>{check.ready ? <Check size={12} /> : index + 1}</i><span>{check.label}</span></div>)}</section>
        </aside>
      </div>

      <RecentOutputs mode={generatorTab} items={generatorTab === 'dynamic' ? generatedPrerolls : generatedComingLists} onPreview={generatorTab === 'dynamic' ? onPreviewDynamic : onPreviewComing} onDelete={generatorTab === 'dynamic' ? onDeleteDynamic : onDeleteComing} />
    </div>
  );
}
