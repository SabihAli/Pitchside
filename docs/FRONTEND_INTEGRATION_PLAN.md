# Implementation Plan — Port `pitchai-analyst.html` design into `services/web`

Working document for the port described in `docs/FRONTEND_INTEGRATION_PROMPT.md`.
Delete both files once the port lands and is verified (same as `UI_PHASE_4.md` /
`FRONTEND_REVAMP.md`).

Scope: presentation layer only. No API contract, hook, or business-logic changes.

---

## 0. Findings from the pre-port audit

Verified against the working tree before planning:

| Fact | Value |
|---|---|
| Prototype size | 1659 lines, 4 view panels (`view-chat`, `view-leagues`, `view-knowledge`, `view-settings`) + match-status rail |
| Prototype palette | dark-only — its `:root` and `.dark` blocks are **identical** |
| Prototype icons | Phosphor **light** weight via jsDelivr CSS (`@phosphor-icons/web@2.1.1/src/light/style.css`), 19 distinct glyphs |
| Web files with `material-symbols-outlined` | 10 (9 `.tsx` + `globals.css`) |
| Web green hexes | 11 occurrences, all inside `globals.css` — no component-level literals |
| Web components total | ~2900 lines across 15 components |
| Web deps | next 15.1.0, react 19, react-markdown, remark-gfm, react-qr-code — no icon package yet |

### Deltas the prompt does not cover (decisions needed)

1. **Two extra screens exist in the live app** that have no prototype counterpart and
   are absent from the prompt's component list, but both use Material Symbols and so
   block the "zero `material-symbols-outlined`" acceptance item:
   - `src/components/live-events/LiveEventsView.tsx` (3 refs) — a locked screen per
     `UI_REQUIREMENTS.md` lines 18/50/394.
   - `src/app/help/page.tsx` (1 ref) — locked per `UI_REQUIREMENTS.md` line 395.

   **Decision: include both in the port**, styled by analogy (Live Events follows the
   leagues card treatment; Help follows the settings panel treatment). Flag in the PR
   that these were extrapolated, not ported from a reference.
2. **`AuthModal.tsx` is out of scope but holds one Material Symbols ref** (a `close`
   glyph). **Decision: swap that single glyph to Phosphor and change nothing else** in
   the auth components — the minimum needed to satisfy the checklist without touching
   the auth visual language, which is `auth-reference.html`'s separate task.
3. **Light mode.** The prototype is dark-only; `globals.css` still carries a full light
   `:root` palette, but `layout.tsx` hardcodes `<html className="dark">`, so light never
   renders. **Decision: mirror the prototype — set `:root` and `.dark` to the same dark
   token values.** This deletes an unreachable palette rather than a live feature.
4. **Icon delivery mechanism.** The prompt allows either. **Decision: `@phosphor-icons/react`**
   (`weight="light"` to match the prototype's `ph-light`), not the CDN font: it keeps
   glyphs tree-shaken and self-hosted, avoids a render-blocking third-party stylesheet
   and an icon-font FOUT, and gives per-icon type safety. Cost: an explicit
   `weight="light"` on every usage (or one thin local wrapper that defaults it).

---

## Phase 1 — Token migration (blocks everything else)

Nothing below can start until this lands; do it as one self-contained commit.

**`services/web/src/app/globals.css`**
- Replace both `:root` and `.dark` bodies with the prototype's shared token block:
  `--background: #0a0a0b`, `--foreground: #e9e8e3`, `--card: #18181b`,
  `--card-foreground: #e9e8e3`, `--border: #303033`, `--input: #303033`,
  `--muted: #1f1f22`, `--muted-foreground: #a3a39e`, `--primary: #b9cf6a`,
  `--primary-foreground: #14210a`, `--secondary: #232326`,
  `--secondary-foreground: #e9e8e3`, `--accent: #b9cf6a`,
  `--accent-foreground: #14210a`, `--ring: #b9cf6a`, `--radius: 3px`,
  `--destructive: #c0392b`, `--destructive-foreground: #f2f1ec`.
- Set `--font-serif: var(--font-sans)` (keep the variable — `.message-markdown`
  headings still apply `font-serif`).
- Carry over the sidebar/chart/popover vars the web app has but the prototype lacks by
  deriving them from the new palette (`--sidebar: #111113` / `surface-container-low`,
  `--sidebar-border: #303033`, `--sidebar-primary: #b9cf6a`, charts from the
  lime/graphite ramp). Do not leave any old green value behind.
- Port the prototype's utility classes verbatim: `.pitch-pattern`, `.liquid-glass`
  (flat: `#18181b` + 1px `#303033`, no `backdrop-filter`), `.kickoff-btn`,
  `.pitch-anim-layer`, `.pitch-content`, `.scrollbar-hide`, and the
  `.sidebar-collapsed` / `.sidebar-search-*` rules.
- Leave the `.material-symbols-outlined` block in place for now; it is deleted in
  Phase 2 step 4 once nothing references it.

**`services/web/tailwind.config.ts`**
- Take option **(a)** from the prompt: extend `theme.extend.colors` with the
  prototype's full semantic set — `card-surface`, `surface`, `surface-sunken`,
  `surface-variant`, `surface-container{,-low,-lowest,-high,-highest}`,
  `surface-bright`, `surface-dim`, `on-surface`, `on-surface-variant`,
  `on-background`, `outline`, `outline-variant`, `accent`, `accent-dim`,
  `off-white`, `error`/`error-container`, `tertiary*`, the `*-fixed*` ramp — using the
  literal hexes from the prototype's inline config. Keep every existing shadcn-style
  `var(--…)` mapping alongside them so no current class breaks.
- Replace `borderRadius` with the locked scale:
  `DEFAULT: 3px, sm: 2px, md: 3px, lg: 3px, xl: 4px, 2xl: 4px, full: 9999px`.
- Point `fontFamily.serif` at the sans stack; keep `sans` and `mono` as-is.
- Add the prototype's `spacing` keys (`sidebar-width: 280px`, `gutter`,
  `container-margin`, `unit`) and its `fontSize`/`fontFamily` headline/body/label
  scale, so ported markup classes resolve without translation.

**`services/web/src/app/layout.tsx`**
- Drop the `Merriweather` import, its loader call, and the `--font-merriweather`
  variable from `<body>`.

**Phase 1 exit check:** `npm run build` succeeds; app renders in the new palette with
old (Material Symbols) icons and old markup still in place.

---

## Phase 2 — Icon migration

1. `npm i @phosphor-icons/react` in `services/web`.
2. Add `src/components/icons.ts` — a single re-export module naming every glyph the app
   uses, so call sites import from one place and the light-weight default lives in one
   spot. Glyph set from the prototype: `CaretDown`, `CaretUp`, `SidebarSimple`,
   `UserPlus`, `Trophy`, `SoccerBall`, `MagnifyingGlass`, `Hourglass`, `ArrowLineRight`,
   `UploadSimple`, `SignOut`, `Question`, `PaperPlaneRight`, `Globe`, `Gear`,
   `ClockCounterClockwise`, `Check`, `ChartLineUp`, `ChartLine`, `Books`, plus `X`
   (for the two `close` glyphs) and `ArrowsClockwise` (for the spinning refresh in
   Live Events).
3. Sweep all 9 `.tsx` files, replacing each `<span className="material-symbols-outlined">`
   with its Phosphor equivalent. Map by the matching spot in the prototype:
   - `AppShell.tsx` (5): nav + sidebar toggle + footer → `SidebarSimple`,
     `MagnifyingGlass`, `Question`, `UserPlus`/`SignOut`, `SoccerBall`.
   - `LeaguesView.tsx` (4) → `Trophy`, `CaretDown`, `MagnifyingGlass`, `Check`.
   - `LiveEventsView.tsx` (3) → `ChartLineUp`, `ClockCounterClockwise`,
     `ArrowsClockwise` (preserve the existing `animate-spin` class on the refreshing
     state).
   - `MatchStatusPanel.tsx` (2) → `Hourglass` + step glyphs.
   - `ChatComposer.tsx` (1) `travel_explore` → `Globe`.
   - `KnowledgeView.tsx` (1) → `UploadSimple`; `SettingsView.tsx` (1) → `Gear`;
     `help/page.tsx` (1) → `Question`; `AuthModal.tsx` (1) `close` → `X`.
   - Note `AppShell`'s nav array passes `{item.icon}` as a string — convert that field
     to a component reference as part of the sweep.
4. Delete the `.material-symbols-outlined` CSS block from `globals.css` and the Google
   Fonts `<link>` from `layout.tsx`.

**Phase 2 exit check:** `grep -r material-symbols-outlined services/web/src` returns
nothing; every screen still renders an icon in every slot it had one before.

---

## Phase 3 — Component ports

One commit per component; each independently reviewable and revertible.

1. **`AppShell.tsx`** — flat `.nav-item` treatment, collapse behavior
   (`sidebar-collapsed`, 88px, hidden `sidebar-text`), Kickoff CTA via `.kickoff-btn`,
   Help / Sign-up-or-Logout footer slot. Copy and auth-state behavior stay exactly as
   `UI_REQUIREMENTS.md` locks them (Kickoff, Match History with relative labels, Your
   Leagues, Ball Knowledge, Live Events). The collapsed search affordance is one of the
   two sanctioned `rounded-full` pill exceptions.
2. **`ChatComposer.tsx`** — solid surface, 1px hairline border, no blur/glow; Phosphor
   mic / `PaperPlaneRight` / `Globe` icons. Send button is the second sanctioned pill.
   Re-verify placeholder, send, and toggle states against WCAG AA on `#18181b`.
3. **`ChatThread.tsx` / `MessageContent.tsx`** — bubble shapes
   (`rounded-xl rounded-tl-sm` / `rounded-tr-sm`); bot avatar = "P" monogram in an
   accent-tinted circle (not a glyph); user avatar = flat initials circle derived from
   the authenticated user via `AuthProvider`, with a defensive fallback for
   empty / single-token / very long names. Port the "Key Insight" callout as the nested
   `bg-surface-container-high`-in-`bg-card-surface` panel **as-is** — an explicit
   product decision, do not flatten it.
4. **`MatchStatusPanel.tsx` / `MatchStatusContext.tsx`** — flat step cards
   (Rewriting → Retrieving → Drafting → Judging). Drive the `animate-pulse` dot from
   real pipeline/WS stage state already in `MatchStatusContext`, not the prototype's
   hardcoded step. This is the one place markup may need a small shape change; keep it
   mechanical and call it out.
5. **`PitchCanvas.tsx`** (new client component) — port `initPitchAnimation`'s canvas-2D
   player-node/passing-ball logic (prototype line ~1425), mounted behind the chat view
   with `.pitch-anim-layer` (opacity .35, `z-0`, `pointer-events: none`) under
   `.pitch-content`; corner watermark via `.pitch-pattern`. Guard with
   `cancelAnimationFrame` on unmount and pause when the tab is hidden so chat scroll
   perf is untouched. **Per `UI_REQUIREMENTS.md` the animation keeps running under
   `prefers-reduced-motion` — an explicit deviation from the usual default; confirm the
   call and state it in the PR description rather than silently deciding either way.**
6. **`LeaguesView.tsx`** — Projects-style layout (title, sort, "New league", search,
   cards) with the `.leagues-*` classes and flat card treatment.
7. **`KnowledgeView.tsx`** — drag-drop dropzone and Chunks / Files / Memory-Tokens stat
   treatment, scoped to the logged-in user (not league/project-scoped), per
   `UI_REQUIREMENTS.md`.
8. **`SettingsView.tsx` / `TwoFactorSetup.tsx`** — `.settings-*` form styling;
   `GET/PUT /settings/api-keys` wiring untouched.
9. **`LiveEventsView.tsx` and `help/page.tsx`** (extrapolated — see Finding 1) — apply
   the ported card and panel treatments; no new visual patterns invented.

---

## Phase 4 — Verification

- `grep -rn "material-symbols-outlined\|4caf50\|1a6b3a\|Merriweather" services/web/src services/web/tailwind.config.ts` → no hits.
- Grep for `rounded-full` across `src`; confirm each hit is a true circle (avatar, icon
  button, status dot, progress ring) or one of the two named pill exceptions.
- Confirm `font-serif` resolves to Montserrat in devtools on a markdown heading.
- `npm run lint` and `npm run build` clean.
- Click through all six screens (chat, leagues, knowledge, settings, live events, help)
  plus the match-status rail, in both `npm run dev` and a production build: no visual
  regression vs `pitchai-analyst.html`, no functional regression vs the pre-port app
  (send a message end-to-end, upload a knowledge file, save an API key, run 2FA setup,
  create a league).
- Confirm each screen's copy, IA, and backend bindings still match
  `UI_REQUIREMENTS.md`'s locked decisions table.

## Phase 5 — Cleanup

Delete `docs/FRONTEND_INTEGRATION_PROMPT.md` and this plan file. The PR description must
call out: the reduced-motion deviation, the two extrapolated screens, the light-palette
collapse, the single auth-icon touch, and any markup-shape change made in
`MatchStatusPanel`.

---

## Risks

| Risk | Mitigation |
|---|---|
| Phase 1 token swap visually breaks screens before their Phase 3 port lands | Expected and temporary; keep Phase 1 as one commit and land Phase 3 in the same PR |
| Prototype's fuller color set collides with existing shadcn key names (`accent`, `primary`, `secondary`) | Phase 1 sets the CSS vars to the same hexes, so either resolution is identical — verify `accent` and `secondary` specifically, where prototype literals differ from the CSS-var intent |
| Canvas animation costs chat scroll perf | Fixed-size canvas, rAF cancelled on unmount, paused when hidden; profile the chat view before/after |
| Initials avatar breaks on unusual names | Defensive derivation in the real component (Phase 3.3), not a token-system change |
