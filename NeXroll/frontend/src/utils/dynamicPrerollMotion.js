const OUTPUT_DIMENSIONS = {
  '720': { width: 1280, height: 720 },
  '1080': { width: 1920, height: 1080 },
  '2160': { width: 3840, height: 2160 },
};

// `at` is the Now Showing connector, the counterpart to Coming Soon's `to`.
// The renderer writes "NOW SHOWING / at / <server>", so the preview has to as
// well or the two disagree. Values match TRANSLATIONS in dynamic_preroll.py.
const COPY = {
  en: { coming: 'COMING SOON', to: 'to', at: 'at', feature: 'FEATURE PRESENTATION', now: 'NOW SHOWING' },
  fr: { coming: 'PROCHAINEMENT', to: 'sur', at: 'sur', feature: 'LONG M\u00c9TRAGE', now: '\u00c0 L\'AFFICHE' },
  es: { coming: 'PR\u00d3XIMAMENTE', to: 'en', at: 'en', feature: 'FUNCI\u00d3N PRINCIPAL', now: 'EN CARTELERA' },
  de: { coming: 'DEMN\u00c4CHST', to: 'auf', at: 'auf', feature: 'HAUPTFILM', now: 'JETZT IM PROGRAMM' },
};

const QUALITY_BITRATES = {
  draft: 5_000_000,
  balanced: 8_000_000,
  high: 12_000_000,
  master: 18_000_000,
};

export const DYNAMIC_FONT_SCALES = [0.85, 1, 1.15, 1.3];

const clamp = value => Math.max(0, Math.min(1, value));
const smoothstep = (start, end, value) => {
  if (end <= start) return value >= end ? 1 : 0;
  const amount = clamp((value - start) / (end - start));
  return amount * amount * (3 - (2 * amount));
};

export const normalizeDynamicColor = (value, fallback) => String(value || fallback).replace(/^0x/i, '#');
export const resolveDynamicOutput = resolution => OUTPUT_DIMENSIONS[String(resolution || '1080')] || OUTPUT_DIMENSIONS['1080'];
export const resolveDynamicFontScale = value => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 1;
  return Math.max(DYNAMIC_FONT_SCALES[0], Math.min(DYNAMIC_FONT_SCALES[DYNAMIC_FONT_SCALES.length - 1], numeric));
};
export const resolveDynamicThemeEffect = theme => String(theme?.effect || 'orbital').toLowerCase();

export function getDynamicFrameState(elapsedSeconds, durationSeconds) {
  const duration = Math.max(1, Number(durationSeconds) || 5);
  const elapsed = Math.max(0, Math.min(duration, Number(elapsedSeconds) || 0));
  const fadeLength = Math.max(0.5, Math.min(1, duration * 0.2));
  return {
    elapsed,
    sceneAlpha: smoothstep(0, fadeLength, elapsed) * (1 - smoothstep(duration - fadeLength, duration, elapsed)),
    titleReveal: smoothstep(0.08, 0.82, elapsed),
    detailReveal: smoothstep(0.22, 1.02, elapsed),
    subjectReveal: smoothstep(0.42, 1.28, elapsed),
    ruleReveal: smoothstep(0.12, 0.92, elapsed),
    driftX: Math.sin((elapsed / 7) * Math.PI * 2),
    driftY: Math.cos((elapsed / 8.5) * Math.PI * 2),
    pulse: 0.55 + (0.45 * Math.sin((elapsed / 1.2) * Math.PI * 2)),
  };
}

const rgba = (value, alpha, fallback) => {
  const normalized = normalizeDynamicColor(value, fallback);
  const short = normalized.match(/^#([0-9a-f]{3})$/i);
  const full = normalized.match(/^#([0-9a-f]{6})$/i);
  const hex = short ? short[1].split('').map(character => character + character).join('') : full?.[1];
  if (!hex) return normalizeDynamicColor(fallback, '#000000');
  const numeric = Number.parseInt(hex, 16);
  return `rgba(${(numeric >> 16) & 255}, ${(numeric >> 8) & 255}, ${numeric & 255}, ${alpha})`;
};

const setFont = (context, size, weight = 700) => {
  context.font = `${weight} ${Math.round(size)}px Inter, "Segoe UI", Arial, sans-serif`;
  context.textAlign = 'center';
  context.textBaseline = 'middle';
};

const setFittedFont = (context, text, desiredSize, maxWidth, weight = 700, spacing = 0) => {
  let size = Math.max(8, desiredSize);
  setFont(context, size, weight);
  const measured = context.measureText(String(text || '')).width + Math.max(0, String(text || '').length - 1) * spacing;
  if (measured > maxWidth && measured > 0) {
    size = Math.max(8, size * (maxWidth / measured));
    setFont(context, size, weight);
  }
  return size;
};

const seededUnit = seed => {
  const value = Math.sin(seed * 12.9898) * 43758.5453;
  return value - Math.floor(value);
};

const drawDynamicThemeBackdrop = (context, width, height, scale, state, theme, colors) => {
  const { primary, secondary, accent } = colors;
  const effect = resolveDynamicThemeEffect(theme);
  context.save();

  if (effect === 'aurora') {
    for (let ribbon = 0; ribbon < 4; ribbon += 1) {
      const gradient = context.createLinearGradient(0, height * 0.15, width, height * 0.72);
      gradient.addColorStop(0, rgba(ribbon % 2 ? secondary : primary, 0, '#00d4ff'));
      gradient.addColorStop(0.35, rgba(ribbon % 2 ? secondary : primary, 0.28, '#00d4ff'));
      gradient.addColorStop(0.72, rgba(ribbon % 2 ? accent : secondary, 0.2, '#7b2cbf'));
      gradient.addColorStop(1, rgba(accent, 0, '#ff006e'));
      context.beginPath();
      for (let step = 0; step <= 16; step += 1) {
        const x = (step / 16) * width;
        const wave = Math.sin((step * 0.68) + (state.elapsed * 0.6) + ribbon) * height * (0.035 + ribbon * 0.006);
        const y = height * (0.25 + ribbon * 0.105) + wave + (state.driftY * 8 * scale);
        if (step === 0) context.moveTo(x, y);
        else context.lineTo(x, y);
      }
      context.strokeStyle = gradient;
      context.lineWidth = height * (0.075 - ribbon * 0.008);
      context.shadowColor = ribbon % 2 ? secondary : primary;
      context.shadowBlur = 34 * scale;
      context.stroke();
    }
  } else if (effect === 'cyber_grid') {
    const horizon = height * 0.59;
    const sun = context.createRadialGradient(width * 0.5, horizon, 0, width * 0.5, horizon, height * 0.23);
    sun.addColorStop(0, rgba(accent, 0.3, '#ff006e'));
    sun.addColorStop(0.52, rgba(secondary, 0.1, '#7b2cbf'));
    sun.addColorStop(1, 'rgba(0,0,0,0)');
    context.fillStyle = sun;
    context.fillRect(0, height * 0.25, width, height * 0.58);
    context.strokeStyle = rgba(primary, 0.28, '#00d4ff');
    context.lineWidth = Math.max(1, scale);
    const travel = (state.elapsed * 0.65) % 1;
    for (let row = 0; row < 13; row += 1) {
      const depth = Math.pow((row + travel) / 13, 2.15);
      const y = horizon + depth * (height - horizon);
      context.beginPath();
      context.moveTo(0, y);
      context.lineTo(width, y);
      context.stroke();
    }
    for (let column = -10; column <= 10; column += 1) {
      context.beginPath();
      context.moveTo(width * 0.5 + column * width * 0.012, horizon);
      context.lineTo(width * 0.5 + column * width * 0.09, height);
      context.stroke();
    }
    context.fillStyle = rgba(accent, 0.18 + (state.pulse * 0.08), '#ff006e');
    for (let index = 0; index < 7; index += 1) {
      const blockWidth = width * (0.035 + seededUnit(index + 20) * 0.075);
      const x = seededUnit(index + 40) * width;
      const y = height * (0.14 + seededUnit(index + 60) * 0.3);
      context.fillRect(x, y, blockWidth, Math.max(1, 2 * scale));
    }
  } else if (effect === 'solar') {
    const flareX = width * (0.78 + state.driftX * 0.012);
    const flareY = height * (0.32 + state.driftY * 0.01);
    const flare = context.createRadialGradient(flareX, flareY, 0, flareX, flareY, height * 0.54);
    flare.addColorStop(0, rgba(primary, 0.38, '#ffd166'));
    flare.addColorStop(0.12, rgba(accent, 0.25, '#ff6b35'));
    flare.addColorStop(0.5, rgba(secondary, 0.08, '#ef233c'));
    flare.addColorStop(1, 'rgba(0,0,0,0)');
    context.fillStyle = flare;
    context.fillRect(0, 0, width, height);
    context.translate(flareX, flareY);
    context.rotate(state.elapsed * 0.025);
    for (let ray = 0; ray < 18; ray += 1) {
      context.rotate((Math.PI * 2) / 18);
      const rayGradient = context.createLinearGradient(0, 0, height * 0.75, 0);
      rayGradient.addColorStop(0, rgba(primary, 0.13, '#ffd166'));
      rayGradient.addColorStop(1, 'rgba(0,0,0,0)');
      context.fillStyle = rayGradient;
      context.beginPath();
      context.moveTo(0, -2 * scale);
      context.lineTo(height * 0.76, -9 * scale);
      context.lineTo(height * 0.76, 9 * scale);
      context.closePath();
      context.fill();
    }
  } else if (effect === 'starfield') {
    for (let index = 0; index < 92; index += 1) {
      const depth = 0.35 + seededUnit(index + 8) * 0.65;
      const x = (seededUnit(index + 101) * width + state.elapsed * 5 * scale * depth) % width;
      const y = seededUnit(index + 211) * height;
      const radius = (0.45 + seededUnit(index + 307) * 1.65) * scale * depth;
      const twinkle = 0.25 + 0.65 * Math.abs(Math.sin(state.elapsed * (0.7 + depth) + index));
      context.fillStyle = rgba(index % 7 === 0 ? accent : primary, twinkle, '#ffffff');
      context.beginPath();
      context.arc(x, y, radius, 0, Math.PI * 2);
      context.fill();
    }
    context.strokeStyle = rgba(secondary, 0.16, '#7b2cbf');
    context.lineWidth = 1.2 * scale;
    for (let ring = 0; ring < 3; ring += 1) {
      context.beginPath();
      context.ellipse(width * 0.5, height * 0.49, width * (0.17 + ring * 0.1), height * (0.06 + ring * 0.035), -0.18, 0, Math.PI * 2);
      context.stroke();
    }
  } else if (effect === 'luxe') {
    const sheen = context.createLinearGradient(0, height, width, 0);
    sheen.addColorStop(0, rgba(secondary, 0.02, '#7b2cbf'));
    sheen.addColorStop(0.48, rgba(primary, 0.18, '#ffd700'));
    sheen.addColorStop(0.53, rgba(accent, 0.05, '#ffffff'));
    sheen.addColorStop(1, rgba(secondary, 0.02, '#7b2cbf'));
    context.fillStyle = sheen;
    context.fillRect(0, 0, width, height);
    context.strokeStyle = rgba(primary, 0.2, '#ffd700');
    context.lineWidth = 1.2 * scale;
    for (let arc = 0; arc < 5; arc += 1) {
      context.beginPath();
      context.ellipse(width * (0.12 + arc * 0.2), height * (0.55 + state.driftY * 0.006), width * 0.28, height * (0.42 + arc * 0.025), -0.62, -1.2, 1.15);
      context.stroke();
    }
    for (let fleck = 0; fleck < 28; fleck += 1) {
      const x = seededUnit(fleck + 501) * width;
      const y = seededUnit(fleck + 601) * height;
      const alpha = 0.12 + 0.28 * Math.abs(Math.sin(state.elapsed * 0.8 + fleck));
      context.fillStyle = rgba(primary, alpha, '#ffd700');
      context.fillRect(x, y, Math.max(1, scale), Math.max(1, scale));
    }
  }

  context.restore();
  return effect;
};

const drawSpacedText = (context, text, centerX, centerY, spacing) => {
  const characters = Array.from(String(text || ''));
  const widths = characters.map(character => context.measureText(character).width);
  const totalWidth = widths.reduce((sum, width) => sum + width, 0) + Math.max(0, characters.length - 1) * spacing;
  let x = centerX - (totalWidth / 2);
  const previousAlign = context.textAlign;
  context.textAlign = 'left';
  characters.forEach((character, index) => {
    context.fillText(character, x, centerY);
    x += widths[index] + spacing;
  });
  context.textAlign = previousAlign;
};

const drawGlowText = (context, text, x, y, color, glow, blur, alpha = 1, spacing = 0) => {
  context.save();
  context.globalAlpha *= alpha;
  context.fillStyle = color;
  context.shadowColor = glow;
  context.shadowBlur = blur;
  if (spacing > 0) drawSpacedText(context, text, x, y, spacing);
  else context.fillText(text, x, y);
  context.restore();
};

const drawLogo = (context, logoImage, centerX, centerY, maxWidth, maxHeight, alpha) => {
  if (!logoImage?.naturalWidth || !logoImage?.naturalHeight) return false;
  const scale = Math.min(maxWidth / logoImage.naturalWidth, maxHeight / logoImage.naturalHeight);
  const width = logoImage.naturalWidth * scale;
  const height = logoImage.naturalHeight * scale;
  context.save();
  context.globalAlpha *= alpha;
  context.drawImage(logoImage, centerX - (width / 2), centerY - (height / 2), width, height);
  context.restore();
  return true;
};

export function drawDynamicPrerollFrame(canvas, options, elapsedSeconds) {
  const context = canvas?.getContext?.('2d');
  if (!context) return;

  const width = canvas.width;
  const height = canvas.height;
  const scale = height / 720;
  const settings = options.settings || {};
  const theme = options.theme || {};
  const template = settings.template || 'coming_soon';
  const duration = Number(settings.duration) || 5;
  const state = getDynamicFrameState(elapsedSeconds, duration);
  const text = COPY[settings.language] || COPY.en;
  const background = normalizeDynamicColor(theme.bg, '#141428');
  const primary = normalizeDynamicColor(theme.primary, '#00d4ff');
  const secondary = normalizeDynamicColor(theme.secondary, '#7b2cbf');
  const accent = normalizeDynamicColor(theme.accent, '#ff006e');
  const titleColor = normalizeDynamicColor(settings.titleColor, primary);
  const subjectColor = normalizeDynamicColor(settings.subjectColor, secondary);
  const fontScale = resolveDynamicFontScale(settings.fontScale);

  context.clearRect(0, 0, width, height);
  context.fillStyle = background;
  context.fillRect(0, 0, width, height);

  const themeEffect = drawDynamicThemeBackdrop(context, width, height, scale, state, theme, {
    primary,
    secondary,
    accent,
  });

  const centerGlow = context.createRadialGradient(width * 0.5, height * 0.45, 0, width * 0.5, height * 0.45, height * 0.34);
  centerGlow.addColorStop(0, rgba(primary, 0.18, '#00d4ff'));
  centerGlow.addColorStop(1, 'rgba(0,0,0,0)');
  context.fillStyle = centerGlow;
  context.fillRect(0, 0, width, height);

  const drawOrb = (x, y, radius, color) => {
    const gradient = context.createRadialGradient(x, y, 0, x, y, radius);
    gradient.addColorStop(0, rgba(color, 0.16, '#00d4ff'));
    gradient.addColorStop(1, 'rgba(0,0,0,0)');
    context.fillStyle = gradient;
    context.beginPath();
    context.arc(x, y, radius, 0, Math.PI * 2);
    context.fill();
  };
  if (themeEffect === 'orbital') {
    drawOrb(width * (0.10 + state.driftX * 0.025), height * (0.10 + state.driftY * 0.018), height * 0.46, secondary);
    drawOrb(width * (0.91 - state.driftX * 0.022), height * (0.91 - state.driftY * 0.02), height * 0.42, accent);
  }

  context.fillStyle = themeEffect === 'cyber_grid' ? 'rgba(255,255,255,0.032)' : 'rgba(255,255,255,0.018)';
  for (let y = 0; y < height; y += Math.max(3, Math.round(3 * scale))) context.fillRect(0, y, width, Math.max(1, scale));

  context.save();
  context.strokeStyle = rgba(primary, 0.10, '#00d4ff');
  context.lineWidth = Math.max(1, scale);
  context.strokeRect(width * 0.07, height * 0.07, width * 0.86, height * 0.86);
  context.restore();

  context.save();
  context.globalAlpha = state.sceneAlpha;
  const centerX = width / 2;
  const subject = settings.server_name || 'YOUR MEDIA SERVER';
  const logoDrawn = options.logoImage && settings.customLogoFilename;

  if (template === 'feature_presentation') {
    const ruleWidth = width * 0.58 * state.ruleReveal;
    const drawRule = y => {
      const gradient = context.createLinearGradient(centerX - ruleWidth / 2, y, centerX + ruleWidth / 2, y);
      gradient.addColorStop(0, 'rgba(0,0,0,0)');
      gradient.addColorStop(0.5, primary);
      gradient.addColorStop(1, 'rgba(0,0,0,0)');
      context.fillStyle = gradient;
      context.fillRect(centerX - ruleWidth / 2, y, ruleWidth, Math.max(1, scale));
    };
    drawRule(height * 0.34);
    const titleSpacing = 5 * scale * fontScale;
    setFittedFont(context, text.feature, 31 * scale * fontScale, width * 0.78, 900, titleSpacing);
    drawGlowText(context, text.feature, centerX, height * 0.43 + ((1 - state.titleReveal) * 15 * scale), titleColor, rgba(titleColor, 0.62, '#00d4ff'), 22 * scale, state.titleReveal, titleSpacing);
    if (!drawLogo(context, logoDrawn ? options.logoImage : null, centerX, height * 0.56, width * 0.42, height * 0.19, state.subjectReveal)) {
      setFittedFont(context, subject, 42 * scale * fontScale, width * 0.78, 900);
      drawGlowText(context, subject, centerX, height * 0.56 + ((1 - state.subjectReveal) * 18 * scale), subjectColor, rgba(subjectColor, 0.55, '#7b2cbf'), 25 * scale, state.subjectReveal);
    }
    drawRule(height * 0.68);
  } else if (template === 'now_showing') {
    const titleSpacing = 5 * scale * fontScale;
    setFittedFont(context, text.now, 32 * scale * fontScale, width * 0.78, 900, titleSpacing);
    drawGlowText(context, text.now, centerX, height * 0.40 + ((1 - state.titleReveal) * 15 * scale), titleColor, rgba(titleColor, 0.62, '#00d4ff'), 22 * scale, state.titleReveal, titleSpacing);
    // Marquee bulbs sit just under the title, freeing the 0.49 line for the
    // connector so this template reads the same way Coming Soon does.
    const startX = centerX - (width * 0.25);
    for (let index = 0; index < 9; index += 1) {
      context.save();
      context.globalAlpha *= state.detailReveal * clamp((index % 2 ? 1 - state.pulse : state.pulse) + 0.35);
      context.fillStyle = secondary;
      context.shadowColor = secondary;
      context.shadowBlur = 10 * scale;
      context.beginPath();
      context.arc(startX + (index * width * 0.0625), height * 0.455, 4 * scale, 0, Math.PI * 2);
      context.fill();
      context.restore();
    }
    setFont(context, 17 * scale * fontScale, 500);
    drawGlowText(context, text.at, centerX, height * 0.52, rgba(titleColor, 0.78, '#ffffff'), 'rgba(0,0,0,0)', 0, state.detailReveal);
    if (!drawLogo(context, logoDrawn ? options.logoImage : null, centerX, height * 0.61, width * 0.42, height * 0.18, state.subjectReveal)) {
      setFittedFont(context, subject, 42 * scale * fontScale, width * 0.78, 900);
      drawGlowText(context, subject, centerX, height * 0.61 + ((1 - state.subjectReveal) * 18 * scale), subjectColor, rgba(subjectColor, 0.55, '#7b2cbf'), 25 * scale, state.subjectReveal);
    }
  } else {
    const titleSpacing = 6 * scale * fontScale;
    setFittedFont(context, text.coming, 34 * scale * fontScale, width * 0.78, 900, titleSpacing);
    drawGlowText(context, text.coming, centerX, height * 0.40 + ((1 - state.titleReveal) * 15 * scale), titleColor, rgba(titleColor, 0.62, '#00d4ff'), 22 * scale, state.titleReveal, titleSpacing);
    setFont(context, 17 * scale * fontScale, 500);
    drawGlowText(context, text.to, centerX, height * 0.49, rgba(titleColor, 0.78, '#ffffff'), 'rgba(0,0,0,0)', 0, state.detailReveal);
    if (!drawLogo(context, logoDrawn ? options.logoImage : null, centerX, height * 0.60, width * 0.42, height * 0.19, state.subjectReveal)) {
      setFittedFont(context, subject, 43 * scale * fontScale, width * 0.78, 900);
      drawGlowText(context, subject, centerX, height * 0.60 + ((1 - state.subjectReveal) * 18 * scale), subjectColor, rgba(subjectColor, 0.55, '#7b2cbf'), 25 * scale, state.subjectReveal);
    }
  }
  context.restore();
}

const loadLogo = async logoUrl => {
  if (!logoUrl) return null;
  return new Promise(resolve => {
    const image = new Image();
    image.crossOrigin = 'anonymous';
    image.onload = () => resolve(image);
    image.onerror = () => resolve(null);
    image.src = logoUrl;
  });
};

export async function prepareDynamicPrerollOptions({ settings, theme, templateName, logoUrl }) {
  if (document.fonts?.ready) await document.fonts.ready;
  const logoImage = settings.customLogoFilename ? await loadLogo(logoUrl) : null;
  return { settings, theme, templateName, logoImage };
}

export function startDynamicPrerollPreview(canvas, options) {
  if (!canvas?.getContext?.('2d')) return () => {};
  canvas.width = 1280;
  canvas.height = 720;
  const duration = Math.max(1, Number(options.settings?.duration) || 5);
  const startedAt = performance.now();
  let animationFrame;
  const paint = now => {
    const elapsed = ((now - startedAt) / 1000) % duration;
    drawDynamicPrerollFrame(canvas, options, elapsed);
    animationFrame = requestAnimationFrame(paint);
  };
  animationFrame = requestAnimationFrame(paint);
  return () => cancelAnimationFrame(animationFrame);
}

const blobToDataUrl = blob => new Promise((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = () => resolve(reader.result);
  reader.onerror = () => reject(reader.error || new Error('Unable to read the recorded animation.'));
  reader.readAsDataURL(blob);
});

export async function recordDynamicPrerollAnimation(options) {
  if (typeof MediaRecorder === 'undefined') return null;
  const dimensions = resolveDynamicOutput(options.settings?.resolution);
  const frameRate = [24, 30, 60].includes(Number(options.settings?.frameRate)) ? Number(options.settings.frameRate) : 30;
  const canvas = document.createElement('canvas');
  canvas.width = dimensions.width;
  canvas.height = dimensions.height;
  if (!canvas.captureStream || !canvas.getContext?.('2d')) return null;

  const mimeType = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm']
    .find(type => MediaRecorder.isTypeSupported(type));
  if (!mimeType) return null;

  const pixels = dimensions.width * dimensions.height;
  const bitrateScale = Math.max(0.55, Math.min(3, pixels / (1920 * 1080)));
  const videoBitsPerSecond = Math.round((QUALITY_BITRATES[options.settings?.renderQuality] || QUALITY_BITRATES.high) * bitrateScale);
  // A zero-rate capture stream lets us request every selected frame explicitly.
  // This avoids background-tab/requestAnimationFrame throttling changing a 24/30/60 fps export.
  let stream = canvas.captureStream(0);
  let videoTrack = stream.getVideoTracks()[0];
  if (typeof videoTrack?.requestFrame !== 'function') {
    stream.getTracks().forEach(track => track.stop());
    stream = canvas.captureStream(frameRate);
    videoTrack = stream.getVideoTracks()[0];
  }
  const recorder = new MediaRecorder(stream, { mimeType, videoBitsPerSecond });
  const chunks = [];
  recorder.addEventListener('dataavailable', event => { if (event.data?.size) chunks.push(event.data); });

  const stopped = new Promise((resolve, reject) => {
    recorder.addEventListener('stop', resolve, { once: true });
    recorder.addEventListener('error', event => reject(event.error || new Error('Unable to record the preview animation.')), { once: true });
  });
  const duration = Math.max(1, Number(options.settings?.duration) || 5);
  drawDynamicPrerollFrame(canvas, options, 0);
  recorder.start(500);
  const startedAt = performance.now();

  if (typeof videoTrack?.requestFrame === 'function') {
    const totalFrames = Math.ceil(duration * frameRate);
    for (let frame = 0; frame <= totalFrames; frame += 1) {
      const targetTime = startedAt + ((frame / frameRate) * 1000);
      const delay = targetTime - performance.now();
      if (delay > 0) await new Promise(resolve => setTimeout(resolve, delay));
      drawDynamicPrerollFrame(canvas, options, Math.min(duration, frame / frameRate));
      videoTrack.requestFrame();
    }
  } else {
    await new Promise(resolve => {
      const paint = now => {
        const elapsed = Math.min(duration, (now - startedAt) / 1000);
        drawDynamicPrerollFrame(canvas, options, elapsed);
        if (elapsed < duration) requestAnimationFrame(paint);
        else resolve();
      };
      requestAnimationFrame(paint);
    });
  }

  await new Promise(resolve => setTimeout(resolve, Math.ceil(1000 / frameRate)));
  recorder.stop();
  await stopped;
  stream.getTracks().forEach(track => track.stop());
  const blob = new Blob(chunks, { type: mimeType });
  if (!blob.size) throw new Error('The animated preview recording was empty.');
  return {
    videoData: await blobToDataUrl(blob),
    mimeType,
    width: dimensions.width,
    height: dimensions.height,
  };
}

export function captureDynamicPrerollFrame(options) {
  const dimensions = resolveDynamicOutput(options.settings?.resolution);
  const canvas = document.createElement('canvas');
  canvas.width = dimensions.width;
  canvas.height = dimensions.height;
  drawDynamicPrerollFrame(canvas, options, Math.max(1.3, (Number(options.settings?.duration) || 5) * 0.5));
  return canvas.toDataURL('image/png', 1);
}
