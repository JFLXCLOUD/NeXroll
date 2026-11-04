// Version helpers. Same order as the backend (backend/self_update.py): a stable
// release follows its pre-releases, alpha < beta < rc.

export const normalizeVersionString = (input) => {
  try {
    if (!input) return '0.0.0';
    let s = String(input).trim();
    s = s.replace(/^v+/i, '');
    return s || '0.0.0';
  } catch {
    return '0.0.0';
  }
};

export const parseSemver = (v) => {
  const s = normalizeVersionString(v);
  const m = s.match(/^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[.-]([a-zA-Z]+)[.-]?(\d+))?/);
  if (!m) return { major: 0, minor: 0, patch: 0, preTag: null, preNum: 0 };
  return {
    major: parseInt(m[1], 10) || 0,
    minor: parseInt(m[2] || '0', 10),
    patch: parseInt(m[3] || '0', 10),
    preTag: m[4] ? m[4].toLowerCase() : null,
    preNum: parseInt(m[5] || '0', 10)
  };
};

export const compareVersions = (a, b) => {
  const va = parseSemver(a);
  const vb = parseSemver(b);
  // Compare major.minor.patch
  if (va.major !== vb.major) return va.major > vb.major ? 1 : -1;
  if (va.minor !== vb.minor) return va.minor > vb.minor ? 1 : -1;
  if (va.patch !== vb.patch) return va.patch > vb.patch ? 1 : -1;
  // Same base version — compare pre-release
  if (!va.preTag && !vb.preTag) return 0; // both stable
  if (!va.preTag) return 1; // a is stable, b is pre-release
  if (!vb.preTag) return -1; // b is stable, a is pre-release
  // Both have pre-release tags
  const preOrder = { alpha: 0, beta: 1, rc: 2 };
  const aRank = preOrder[va.preTag] ?? 99;
  const bRank = preOrder[vb.preTag] ?? 99;
  if (aRank !== bRank) return aRank > bRank ? 1 : -1;
  if (va.preNum !== vb.preNum) return va.preNum > vb.preNum ? 1 : -1;
  return 0;
};
