import React, { useCallback, useEffect, useRef, useState } from 'react';

// The Konami code's reward: the house lights dim, a velvet curtain swings
// closed over the app and an intermission card comes up. Any click, Escape,
// Enter or Space flies the curtain out upward again.
//
// Each curtain is a row of folds simulated as springs that also hang like
// pendulums from the top: the inner edge leads, the outer folds follow and
// settle, and every fold swings from the curtain's acceleration. A slow draft
// keeps them moving while the curtain is closed; on the way out the curtain
// rises behind the valance with its hem lagging. Styles are written straight
// to the DOM from one animation loop, not through React state.
//
// With prefers-reduced-motion (Windows "Animation effects" off, for one) it
// plays a gentle version: the curtain still slides closed and rises, but
// smoothly, with no overshoot, sway, swing or rippling hem (index.css stops the
// popcorn, bulbs and bounces). The Konami code is a deliberate request for it.
const FOLDS = 12;              // per side
const FOLD_OVERLAP = 1.4;      // fold width / spacing, so swinging folds never part
const MIN_BUNCH = 0.15;        // closest two folds get when the curtain is drawn back

// The draw: one spring for how far the curtain is pulled closed (0 = drawn
// back, 1 = closed), slightly underdamped so the curtain bumps past and back.
const DRAW_FREQ = 6.4;         // rad/s
const DRAW_DAMPING = 0.72;     // damping ratio
// Each fold follows its spot on the taut cloth through a quick spring, so the
// folds jostle a little behind the leading edge instead of moving as one.
const FOLD_K = 240;
const FOLD_DAMP = 14;
// The swing of a fold hanging from its top edge.
const SWING_K = 34;
const SWING_DAMP = 2.1;
const SWING_FROM_ACCEL = 0.0065;    // deg/s^2 of swing per px/s^2 of the fold's acceleration
const SWING_MAX = 11;
// Flying out: a short dip, then a steady upward pull.
const DIP_SECONDS = 0.13;
const DIP_ACCEL = 1100;
const LIFT_ACCEL = -3900;
// The gentle version: critically damped, so the curtain stops without a bump,
// and a plain eased rise.
const GENTLE_DRAW_FREQ = 5.2;
const GENTLE_LIFT_SECONDS = 0.95;
const easeInOutCubic = (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);
// The hem lags behind the lift.
const HEM_K = 70;
const HEM_DAMP = 7;
const HEM_FROM_ACCEL = 0.05;

const prefersReducedMotion = () => (
  typeof window !== 'undefined' && window.matchMedia
  && window.matchMedia('(prefers-reduced-motion: reduce)').matches
);

export default function Intermission({ onClose, unlockedTheme }) {
  const [stage, setStage] = useState('closing');   // closing -> open (card up) -> lifting -> leaving
  const rootRef = useRef(null);
  const foldRefs = useRef([]);
  const sim = useRef(null);
  const reduced = useRef(prefersReducedMotion());

  const close = useCallback(() => {
    const s = sim.current;
    if (!s || s.phase === 'lifting' || s.phase === 'leaving') return;
    s.phase = 'lifting';
    s.liftStart = s.t;
    s.vy = 0;
    // The jolt of the fly line sets the folds swinging a little.
    if (!reduced.current) s.folds.forEach((f, i) => { f.va += (i % 2 ? 1 : -1) * (14 + (i % 3) * 6); });
    setStage('lifting');
  }, []);

  useEffect(() => {
    rootRef.current?.focus();
    const onKey = (event) => {
      if (event.key === 'Escape' || event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        close();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [close]);

  useEffect(() => {
    const width = () => window.innerWidth;
    const height = () => window.innerHeight;
    const spacing = () => width() / 2 / FOLDS;
    // Fold i (0 = outer edge, FOLDS - 1 = the edge that meets the other side).
    const closedX = (i) => i * spacing();
    const openX = (i) => -width() / 2 - spacing() * 2 + i * spacing() * 0.18;
    const gentle = reduced.current;
    const folds = Array.from({ length: FOLDS }, (_, i) => ({
      x: openX(i), vx: 0,
      a: 0, va: 0, hem: 0, vhem: 0,
      hemScale: 0.75 + ((i * 7) % 5) / 8,      // fixed per-fold variety for the hem ripple
    }));
    sim.current = { t: 0, phase: 'closing', folds, y: 0, vy: 0, liftStart: 0, u: 0, vu: 0 };

    const paint = () => {
      const s = sim.current;
      const w = spacing() * FOLD_OVERLAP;
      folds.forEach((f, i) => {
        const left = foldRefs.current[i];
        const right = foldRefs.current[FOLDS + i];
        const y = s.y + f.hem;
        if (left) left.style.transform = `translate3d(${f.x}px, ${y}px, 0) rotate(${f.a}deg)`;
        // The right curtain mirrors the left, plus a drift of its own once
        // closed, so the two halves don't sway in perfect lockstep.
        const drift = !gentle && s.t > 1.2 ? 0.45 * Math.sin(s.t * 1.25 + i * 0.75 + 1.7) : 0;
        if (right) right.style.transform = `translate3d(${width() - f.x - w}px, ${y}px, 0) rotate(${-f.a + drift}deg)`;
        if (left) left.style.width = `${w}px`;
        if (right) right.style.width = `${w}px`;
      });
    };

    let frame = 0;
    let last = performance.now();
    let opened = false;
    const step = (now) => {
      const s = sim.current;
      const dt = Math.min(0.033, (now - last) / 1000);
      last = now;
      s.t += dt;
      const t = s.t;

      let liftAccel = 0;
      if (s.phase === 'lifting') {
        const since = t - s.liftStart;
        if (gentle) {
          s.y = -(height() + 160) * easeInOutCubic(Math.min(1, since / GENTLE_LIFT_SECONDS));
        } else {
          liftAccel = since < DIP_SECONDS ? DIP_ACCEL : LIFT_ACCEL;
          s.vy += liftAccel * dt;
          s.y += s.vy * dt;
        }
      }

      // 1. The draw: the leading edge rides one spring; the cloth unfolds from
      //    it, so a fold only starts moving once the fabric reaches it.
      const freq = gentle ? GENTLE_DRAW_FREQ : DRAW_FREQ;
      const damping = gentle ? 1 : DRAW_DAMPING;
      s.vu += (freq * freq * (1 - s.u) - 2 * damping * freq * s.vu) * dt;
      s.u += s.vu * dt;
      const gap = spacing();
      const lead = openX(FOLDS - 1) + s.u * (closedX(FOLDS - 1) - openX(FOLDS - 1));
      const before = folds.map(f => f.vx);
      folds.forEach((f, i) => {
        const target = Math.max(openX(i), lead - (FOLDS - 1 - i) * gap);
        if (gentle) { f.x = target; f.vx = 0; return; }
        // A draft while closed: a slow, travelling push across the folds.
        const draft = t > 1.2 ? 160 * Math.sin(t * 1.35 + i * 0.5) + 90 * Math.sin(t * 0.7 + i * 1.1) : 0;
        f.vx += (FOLD_K * (target - f.x) - FOLD_DAMP * f.vx + draft) * dt;
        f.x += f.vx * dt;
      });
      // 2. The fabric is one piece: neighbouring folds can't part further than
      //    the cloth between them, or bunch tighter than it folds.
      for (let i = FOLDS - 2; i >= 0; i--) {
        const leadFold = folds[i + 1];
        const f = folds[i];
        if (leadFold.x - f.x > gap) f.x = leadFold.x - gap;
        if (leadFold.x - f.x < gap * MIN_BUNCH) f.x = leadFold.x - gap * MIN_BUNCH;
      }
      // 3. Swing: a pendulum hung from the top, driven by how the fold actually
      //    accelerated (it lags as it speeds up, swings through as it stops,
      //    and jumps when the cloth snaps taut).
      if (!gentle) folds.forEach((f, i) => {
        const accel = Math.max(-60000, Math.min(60000, (f.vx - before[i]) / dt));
        const breeze = t > 1.2 ? 22 * Math.sin(t * 1.6 + i * 0.6) : 0;
        const aa = -SWING_K * f.a - SWING_DAMP * f.va + SWING_FROM_ACCEL * accel + breeze;
        f.va += aa * dt;
        f.a = Math.max(-SWING_MAX, Math.min(SWING_MAX, f.a + f.va * dt));
        // 4. Hem: lags behind the lift, each fold a little differently.
        if (s.phase === 'lifting') {
          const ah = -HEM_K * f.hem - HEM_DAMP * f.vhem - HEM_FROM_ACCEL * liftAccel * f.hemScale;
          f.vhem += ah * dt;
          f.hem += f.vhem * dt;
        }
      });
      paint();

      if (!opened && t > (gentle ? 0.95 : 0.75)) { opened = true; setStage('open'); }
      if (s.phase === 'lifting' && s.y <= -(height() + 160)) {
        s.phase = 'leaving';
        setStage('leaving');
        setTimeout(onClose, 520);
        return;
      }
      frame = requestAnimationFrame(step);
    };
    paint();
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
    // The simulation runs once per mount; onClose is only read at the end.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      ref={rootRef}
      className={`nx-intermission is-${stage}`}
      role="dialog"
      aria-modal="true"
      aria-label="Intermission"
      tabIndex={-1}
      onClick={close}
    >
      <div className="nx-intermission-stage" aria-hidden="true">
        {Array.from({ length: FOLDS * 2 }, (_, i) => (
          <span
            key={i}
            className={`nx-intermission-fold${i >= FOLDS ? ' is-right' : ''}`}
            ref={el => { foldRefs.current[i] = el; }}
          />
        ))}
      </div>
      <div className="nx-intermission-valance" aria-hidden="true"><span /></div>
      <div className="nx-intermission-card">
        <div className="nx-intermission-popcorn" aria-hidden="true">
          <span className="kernels">{Array.from({ length: 9 }, (_, i) => <i key={i} />)}</span>
          <span className="bucket" />
        </div>
        <span className="nx-intermission-kicker">The feature will resume shortly</span>
        <h2>Intermission</h2>
        <p>Stretch your legs. Visit the snack bar. Your prerolls will wait.</p>
        {unlockedTheme && (
          <p className="nx-intermission-unlock">
            Secret unlocked: the {unlockedTheme} theme is now in Settings &gt; General.
          </p>
        )}
        <span className="nx-intermission-hint">Click anywhere to raise the curtain</span>
      </div>
    </div>
  );
}
