"use client";

import { useEffect, useRef } from "react";

/**
 * Ported from `docs/design-reference/pitchai-analyst.html`'s `initPitchAnimation`
 * (Phase 3 step 5 of FRONTEND_INTEGRATION_PLAN.md): a canvas-2D layer of wandering
 * player nodes with a ball passed between them, mounted behind the chat view via
 * `.pitch-anim-layer`.
 *
 * Simplification vs. the prototype: the pointer drag/hover interactivity on
 * individual nodes is not ported — this layer is `pointer-events: none` (see
 * `.pitch-anim-layer` in globals.css) and purely decorative here, so only the
 * passive wander + pass-the-ball simulation is kept.
 *
 * Per UI_REQUIREMENTS.md, this animation keeps running under
 * `prefers-reduced-motion` — an explicit, confirmed deviation from the usual
 * default of honoring that media query.
 */
type Player = { x: number; y: number; vx: number; vy: number };

const INITIAL_PLAYERS: Player[] = [
  { x: 0.18, y: 0.28, vx: 0.00004, vy: 0.000027 },
  { x: 0.28, y: 0.48, vx: -0.000033, vy: 0.000033 },
  { x: 0.22, y: 0.68, vx: 0.00003, vy: -0.000023 },
  { x: 0.38, y: 0.35, vx: 0.000027, vy: -0.00003 },
  { x: 0.42, y: 0.58, vx: -0.000037, vy: -0.000023 },
  { x: 0.48, y: 0.78, vx: 0.00003, vy: 0.00002 },
  { x: 0.55, y: 0.3, vx: -0.000027, vy: 0.000033 },
  { x: 0.58, y: 0.52, vx: 0.000033, vy: -0.000027 },
  { x: 0.68, y: 0.4, vx: -0.00003, vy: 0.000023 },
  { x: 0.72, y: 0.62, vx: 0.000037, vy: -0.00002 },
  { x: 0.78, y: 0.48, vx: -0.000023, vy: 0.00003 },
];

export function PitchCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const el = canvasRef.current;
    const parent = el?.parentElement;
    const context = el?.getContext("2d");
    if (!el || !parent || !context) return;
    const canvas = el;
    const main = parent;
    const ctx = context;

    const players = INITIAL_PLAYERS.map((p) => ({ ...p }));
    let carrier = 0;
    const ball = { x: players[0].x, y: players[0].y };
    let passTo = 1;
    let passT = 0;
    let passing = false;
    let rafId = 0;
    let paused = false;

    function pickReceiver(from: number) {
      let next = from;
      while (next === from) next = Math.floor(Math.random() * players.length);
      return next;
    }

    function resize() {
      const rect = main.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.floor(rect.width * dpr);
      canvas.height = Math.floor(rect.height * dpr);
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function tick() {
      if (paused) return;
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      ctx.clearRect(0, 0, w, h);

      for (const p of players) {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0.12 || p.x > 0.88) p.vx *= -1;
        if (p.y < 0.18 || p.y > 0.82) p.vy *= -1;
      }

      if (!passing && Math.random() < 0.004) {
        passing = true;
        passTo = pickReceiver(carrier);
        passT = 0;
      }

      if (passing) {
        passT += 0.004;
        const a = players[carrier];
        const b = players[passTo];
        const t = Math.min(1, passT);
        const ease = t * t * (3 - 2 * t);
        ball.x = a.x + (b.x - a.x) * ease;
        ball.y = a.y + (b.y - a.y) * ease;
        if (t >= 1) {
          carrier = passTo;
          passing = false;
        }
      } else {
        ball.x = players[carrier].x;
        ball.y = players[carrier].y;
      }

      players.forEach((p, i) => {
        const r = i === carrier ? 13.5 : 10.5;
        ctx.beginPath();
        ctx.arc(p.x * w, p.y * h, r, 0, Math.PI * 2);
        ctx.fillStyle =
          i === carrier ? "rgba(120, 220, 119, 0.45)" : "rgba(214, 231, 214, 0.28)";
        ctx.fill();
      });

      ctx.beginPath();
      ctx.arc(ball.x * w, ball.y * h, 9, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(240, 235, 229, 0.55)";
      ctx.fill();

      rafId = requestAnimationFrame(tick);
    }

    function onVisibilityChange() {
      paused = document.hidden;
      if (!paused) rafId = requestAnimationFrame(tick);
    }

    resize();
    window.addEventListener("resize", resize);
    document.addEventListener("visibilitychange", onVisibilityChange);
    rafId = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(rafId);
      window.removeEventListener("resize", resize);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, []);

  return (
    <canvas ref={canvasRef} className="pitch-anim-layer" aria-hidden="true" />
  );
}
