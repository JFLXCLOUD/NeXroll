import {
  drawDynamicPrerollFrame,
  getDynamicFrameState,
  normalizeDynamicColor,
  resolveDynamicFontScale,
  resolveDynamicOutput,
  resolveDynamicThemeEffect,
} from './dynamicPrerollMotion';

const createCanvas = () => {
  const gradient = { addColorStop: jest.fn() };
  const context = {
    arc: jest.fn(),
    beginPath: jest.fn(),
    clearRect: jest.fn(),
    closePath: jest.fn(),
    createLinearGradient: jest.fn(() => gradient),
    createRadialGradient: jest.fn(() => gradient),
    drawImage: jest.fn(),
    ellipse: jest.fn(),
    fill: jest.fn(),
    fillRect: jest.fn(),
    fillText: jest.fn(),
    lineTo: jest.fn(),
    measureText: jest.fn(text => ({ width: String(text).length * 24 })),
    moveTo: jest.fn(),
    restore: jest.fn(),
    rotate: jest.fn(),
    save: jest.fn(),
    stroke: jest.fn(),
    strokeRect: jest.fn(),
    translate: jest.fn(),
  };
  context.paintedText = [];
  context.fillText.mockImplementation(text => context.paintedText.push({ text, color: context.fillStyle }));
  return { width: 1280, height: 720, getContext: jest.fn(() => context) };
};

test('resolves supported dynamic output sizes with a safe default', () => {
  expect(resolveDynamicOutput('720')).toEqual({ width: 1280, height: 720 });
  expect(resolveDynamicOutput('2160')).toEqual({ width: 3840, height: 2160 });
  expect(resolveDynamicOutput('cinema')).toEqual({ width: 1920, height: 1080 });
});

test('normalizes backend hex colors for the shared canvas renderer', () => {
  expect(normalizeDynamicColor('0x00d4ff', '#ffffff')).toBe('#00d4ff');
  expect(normalizeDynamicColor('', '#141428')).toBe('#141428');
});

test('normalizes broadcast-safe dynamic font scales', () => {
  expect(resolveDynamicFontScale(0.85)).toBe(0.85);
  expect(resolveDynamicFontScale(1.3)).toBe(1.3);
  expect(resolveDynamicFontScale(0.2)).toBe(0.85);
  expect(resolveDynamicFontScale(4)).toBe(1.3);
  expect(resolveDynamicFontScale('not-a-size')).toBe(1);
});

test('selects motion effects from themes with an orbital fallback', () => {
  expect(resolveDynamicThemeEffect({ effect: 'aurora' })).toBe('aurora');
  expect(resolveDynamicThemeEffect({ effect: 'CYBER_GRID' })).toBe('cyber_grid');
  expect(resolveDynamicThemeEffect({})).toBe('orbital');
});

test.each(['orbital', 'aurora', 'cyber_grid', 'solar', 'starfield', 'luxe'])(
  'draws the %s theme at extra-large type scale without leaving the safe renderer',
  effect => {
    const canvas = createCanvas();
    expect(() => drawDynamicPrerollFrame(canvas, {
      settings: {
        template: 'coming_soon',
        server_name: 'A Long Home Cinema Server Name',
        duration: 5,
        language: 'en',
        fontScale: 1.3,
      },
      theme: {
        effect,
        bg: '0x050816',
        primary: '0xdff6ff',
        secondary: '0x6c63ff',
        accent: '0xffcc66',
      },
      templateName: 'Coming Soon',
    }, 2.5)).not.toThrow();
  }
);

test('uses custom text colors and omits editor-only corner labels', () => {
  const canvas = createCanvas();
  const context = canvas.getContext('2d');
  drawDynamicPrerollFrame(canvas, {
    settings: {
      template: 'coming_soon',
      server_name: 'NeXroll Cinema',
      duration: 5,
      language: 'en',
      titleColor: '#112233',
      subjectColor: '#ddeeff',
    },
    theme: {
      effect: 'orbital',
      bg: '0x050816',
      primary: '0x00d4ff',
      secondary: '0x6c63ff',
      accent: '0xffcc66',
    },
    templateName: 'EDITOR LABEL',
  }, 2.5);

  expect(context.paintedText.some(item => item.text === 'C' && item.color === '#112233')).toBe(true);
  expect(context.paintedText.some(item => item.text === 'NeXroll Cinema' && item.color === '#ddeeff')).toBe(true);
  expect(context.paintedText.map(item => item.text)).not.toContain('EDITOR LABEL');
  expect(context.paintedText.map(item => item.text)).not.toContain('5s');
});

test('motion state fades the same shared scene in and out', () => {
  const start = getDynamicFrameState(0, 5);
  const middle = getDynamicFrameState(2.5, 5);
  const end = getDynamicFrameState(5, 5);
  expect(start.sceneAlpha).toBe(0);
  expect(middle.sceneAlpha).toBe(1);
  expect(middle.subjectReveal).toBe(1);
  expect(end.sceneAlpha).toBe(0);
});
