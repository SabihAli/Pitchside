# Prompt: Port the `pitchai-analyst.html` design revamp into `services/web`

> Paste this whole file as the task prompt for the session that does the port.
> It is self-contained — it does not depend on the (now-deleted) `FRONTEND_REVAMP.md`
> phase log, only on the finished artifacts it references below.

## Goal

`docs/design-reference/pitchai-analyst.html` is a standalone, no-build-step HTML/Tailwind-CDN
prototype that has been through a full anti-AI-tell design revamp (neutral graphite/zinc
palette with one desaturated lime accent, one icon family, one locked radius scale, flat
surfaces, a restrained pitch motif, monogram/initials avatars). It is **not wired to any
backend** and only exists to lock the visual direction.

The live product is the Next.js app at `services/web/`, which still uses the **pre-revamp**
design language: saturated pitch-green (`#4caf50` / `#1a6b3a`), Merriweather serif headings,
Material Symbols icons, default shadcn-style radii, glassy/generic surfaces. Your job is to
port the prototype's finished visual language and markup patterns into `services/web`'s real,
data-wired components — **without regressing any functionality** the live app already has.

This is a presentation-layer port. Do not change API contracts, hooks, or business logic
unless a component's markup structure genuinely needs to change shape to carry the new design.

## Source of truth (read these first, in order)

1. `docs/design-reference/pitchai-analyst.html` — the finished visual reference. Read the
   entire `<style>` block (design-token comments at the top are load-bearing) and the full
   markup for all five views: chat, leagues, ball knowledge, settings, match-status rail.
2. `docs/design-reference/theme.css` — the token file the prototype's `<link>` pulls in;
   already swept to match (no leftover Merriweather/pitch-green).
3. `docs/UI_REQUIREMENTS.md` — the **locked product/UX decisions** for the real Phase 8
   frontend (copy, IA, auth flow, per-screen backend bindings). Treat this as authoritative
   for *behavior and copy*; treat the HTML prototype as authoritative for *visual language*.
   Where the two conflict on a purely visual detail (e.g. a color), the HTML prototype wins.
4. `docs/PHASE_8_PLAN.md` — workstream/backend-binding context if you need it.
5. The current `services/web` implementation (read before touching anything):
   - `services/web/src/app/globals.css` — current (pre-revamp) CSS variables.
   - `services/web/tailwind.config.ts` — current Tailwind theme mapping.
   - `services/web/src/components/shell/AppShell.tsx` — sidebar/nav shell.
   - `services/web/src/components/chat/ChatComposer.tsx`, `ChatThread.tsx`,
     `MessageContent.tsx`, `MatchStatusPanel.tsx`, `MatchStatusContext.tsx`,
     `HomeKickoff.tsx` — chat view + match-status rail.
   - `services/web/src/components/leagues/LeaguesView.tsx` — leagues screen.
   - `services/web/src/components/knowledge/KnowledgeView.tsx` — ball knowledge screen.
   - `services/web/src/components/settings/SettingsView.tsx`,
     `TwoFactorSetup.tsx` — settings screen.
   - `services/web/src/components/auth/AuthModal.tsx`, `AuthProvider.tsx` — auth flow
     (visual reference for this one is `docs/design-reference/auth-reference.html`, a
     separate prototype — out of scope for this pass unless you're explicitly asked to
     include it too).

## Token migration (do this first — everything else depends on it)

`services/web/src/app/globals.css` `:root`/`.dark` blocks and `tailwind.config.ts`'s
`theme.extend.colors` currently mirror the *old* shadcn-style palette. Replace their values
with the prototype's tokens (see `pitchai-analyst.html`'s inline `:root, .dark` block and its
Tailwind `theme.extend.colors` config script tag for the exact hex values — background
`#0a0a0b`, card `#18181b`, accent/primary/ring `#b9cf6a`, border `#303033`, muted
`#1f1f22`, etc.). Concretely:

- Collapse `--font-serif` to alias `--font-sans` (Montserrat) — do not remove the CSS
  variable (it's still referenced by `message-markdown` headings via `font-serif`), just
  point it at the sans stack like the prototype does. Do not introduce a new font family;
  the prototype kept Montserrat as the single sans stack, it only dropped Merriweather.
- Update `tailwind.config.ts`'s `borderRadius` scale to the locked scale: containers/cards/
  inputs/buttons sharp (3–4px), `rounded-full` reserved for true circles (avatars, icon
  buttons, status dots) plus exactly two intentional pill exceptions (composer send button,
  collapsed sidebar search affordance) — see the prototype's inline Tailwind config
  `borderRadius` override for the exact scale (`DEFAULT/md/lg: 3px`, `xl/2xl: 4px`,
  `full: 9999px`) and port that mapping in.
- The prototype's Tailwind config also defines a much larger semantic color palette
  (`card-surface`, `surface-container-high`, `on-surface-variant`, `outline-variant`,
  `accent-dim`, etc.) beyond the shadcn set `services/web` currently has. Decide whether to
  (a) extend `tailwind.config.ts`'s `colors` block with the prototype's fuller token set so
  component markup can port near-verbatim, or (b) translate each prototype class to the
  nearest existing shadcn-style token. **Prefer (a)** — it keeps the port mechanical and
  low-risk, and avoids subtly drifting the color values during translation.

## Icon migration

Replace Material Symbols Outlined with Phosphor Icons everywhere, matching the prototype:

1. Add the Phosphor web-font/CSS `<link>` the same way the prototype does (via
   `services/web/src/app/layout.tsx`'s `<head>`, or a proper npm package
   `@phosphor-icons/react` if you'd rather have tree-shaken React components than a global
   icon font — either is fine, but be consistent across every screen).
2. Sweep every component under `services/web/src/components/` and `src/app/` for
   `material-symbols-outlined` spans and replace with the Phosphor equivalent glyph used in
   the matching spot in `pitchai-analyst.html` (sidebar nav, composer mic/send/web-search
   toggle, match-status step icons, leagues/knowledge/settings icons).
3. Delete the now-unused `.material-symbols-outlined` CSS block and its Google Fonts
   `<link>` from `globals.css`/`layout.tsx` once nothing references it.

## Component-by-component porting notes

- **`AppShell.tsx`** (left sidebar / nav): port the flat nav-item treatment (`.nav-item` in
  the prototype), the collapse behavior, the "Kickoff" CTA button styling, and the
  Help/Sign-up-or-Logout footer slot exactly as laid out in `UI_REQUIREMENTS.md`'s locked
  decisions table — that doc governs copy and auth-state behavior; the prototype governs the
  flat/hairline-border visual treatment (no `backdrop-filter` glass).
- **`ChatComposer.tsx`**: currently a plain `rounded-full` pill with a Material Symbols
  `travel_explore` toggle. Port the prototype's flattened composer (post its own Phase 3):
  solid surface, 1px hairline border, no blur/glow, Phosphor icons for mic/send/web-search,
  same WCAG-AA-checked contrast on placeholder/send/toggle states.
- **`ChatThread.tsx` / `MessageContent.tsx`**: port the message-bubble shapes
  (`rounded-xl rounded-tl-sm` / `rounded-tr-sm`), the bot avatar (small "P" monogram in an
  accent-tinted circle, **not** an icon-library glyph) and the user avatar (flat
  initials-in-circle — the real app should use the authenticated user's actual initials, not
  the prototype's placeholder "M"). Note: the prototype's "Key Insight" callout was
  deliberately **kept as a nested card** (not broken out to a border-rule treatment) per an
  explicit product decision during the revamp — port it as the nested
  `bg-surface-container-high`-in-`bg-card-surface` panel exactly as it appears in the
  prototype today, don't "fix" it to a flatter treatment.
- **`MatchStatusPanel.tsx` / `MatchStatusContext.tsx`**: port the flat step-card treatment
  (`Rewriting` → `Retrieving` → `Drafting` → `Judging`), including the `animate-pulse` dot on
  whichever step is genuinely active/streaming (this is real-data-driven in the live app —
  wire the pulse to actual pipeline/WS stage state, don't hardcode it to one step the way the
  static prototype does).
- **Pitch canvas (`#pitch-anim`)**: port `initPitchAnimation`'s canvas-2D logic
  (player nodes + passing ball) into a small client component (e.g.
  `PitchCanvas.tsx`) mounted behind the chat view, matching the prototype's
  `.pitch-anim-layer` opacity/z-index treatment and the restrained corner-watermark
  background from `.pitch-pattern`. Per `UI_REQUIREMENTS.md`, prefer keeping this animation
  running even under `prefers-reduced-motion` in the production build (confirm this is still
  the desired call before shipping — it's an explicit deviation from the usual
  reduced-motion default, so flag it in your PR description rather than silently complying
  either way).
- **`LeaguesView.tsx`**: port the Projects-style layout (title, sort, "New league", search,
  cards) using the prototype's `.leagues-*` classes and flat card treatment.
- **`KnowledgeView.tsx`**: port the drag-drop dropzone and Chunks/Files/Memory-Tokens stat
  treatment from the prototype's ball-knowledge view, scoped to the logged-in user's data
  exactly as `UI_REQUIREMENTS.md` specifies (not league/project-scoped).
- **`SettingsView.tsx` / `TwoFactorSetup.tsx`**: port the API-keys form styling
  (`.settings-*` classes), keep the existing `GET/PUT /settings/api-keys` wiring untouched.
- **Auth (`AuthModal.tsx`, `AuthProvider.tsx`)**: out of scope for *this* pass — the visual
  reference for auth is the separate `auth-reference.html` prototype, not
  `pitchai-analyst.html`. Don't touch these unless asked to port that prototype too.

## Explicit non-goals for this pass

- No backend/API changes. If a component's data-fetching or state logic needs to shift
  shape to accommodate new markup, keep the change as small and mechanical as possible and
  call it out explicitly rather than opportunistically refactoring.
- Don't touch `docs/design-reference/auth-reference.html` or port it — separate task.
- Don't re-litigate any visual decision already locked in the prototype (colors, icon
  family, radius scale, avatar treatment) — port them as-is. If something in the prototype
  looks wrong once it's live with real data (e.g. long usernames breaking the initials
  avatar), fix the *real* component defensively, but don't redesign the token system.

## Acceptance checklist

- [ ] `services/web/src/app/globals.css` and `tailwind.config.ts` use the prototype's token
      values (background/card/border/muted/primary-accent/ring), not the old green palette.
- [ ] Zero `material-symbols-outlined` references remain anywhere in `services/web/src`.
- [ ] Zero literal `#4caf50` / `#1a6b3a` / other saturated pitch-green hexes remain anywhere
      in `services/web/src` (styles, inline colors, or Tailwind arbitrary-value classes).
- [ ] `font-serif` no longer renders an actual serif face anywhere in the live app.
- [ ] One radius scale holds across all five ported screens; `rounded-full` appears only on
      true circles plus the two named pill exceptions.
- [ ] Bot messages show the monogram avatar; user messages show real-initials avatars (not a
      stock image, not a generic icon).
- [ ] The pitch canvas animation runs behind the live chat view without regressing chat
      scroll/layout performance.
- [ ] Every screen's copy, IA, and backend bindings still match `docs/UI_REQUIREMENTS.md`'s
      locked decisions table — this port must not silently change product behavior.
- [ ] A full click-through of all five views in both the running dev server and a production
      build, confirming no visual regression versus `pitchai-analyst.html` and no functional
      regression versus the pre-port `services/web`.

Once this port lands and is verified, this file (`docs/FRONTEND_INTEGRATION_PROMPT.md`)
should be deleted the same way `docs/UI_PHASE_4.md` and `docs/FRONTEND_REVAMP.md` were —
it's working context, not permanent documentation.
