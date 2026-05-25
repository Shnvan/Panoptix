# Panoptix Frontend Design System

> **Source of truth**: This document defines the visual identity for all Panoptix frontend work.
> The color philosophy is derived from the [BSIT 2-2 class site](file:///C:/Projects/bsit%202-2%20site), adapted for a CCTV dashboard / security operations interface.

---

## Color Philosophy — Core Principle

**Monochromatic dark base + single warm orange accent.**

Every surface is a shade of pure black or neutral gray. The only chromatic accent color is a warm orange (`#F07C1E`). Status colors (success, warning, error) exist for semantic meaning only — they never compete with the brand accent for visual dominance.

No blue-tinted backgrounds. No cyan. No gradients as decoration. No multi-color accent system.

### The Three Rules

1. **Pure blacks and grays only** — no blue undertone in any background, card, or border.
2. **One accent color** — warm orange `#F07C1E` for brand, navigation, focus, and emphasis.
3. **Sharp geometry** — minimal border-radius (`0` or `2px`), hard edges, no rounded SaaS cards.

---

## Design Tokens — Complete Reference

### Brand / Accent

| Token | CSS Variable | Value | Usage |
|---|---|---|---|
| Brand primary | `--color-brand` | `#F07C1E` | Active nav, focus rings, primary buttons, accent text, scrollbar thumb |
| Brand hover | `--color-brand-hover` | `#C45E0A` | Hover/pressed states for brand-colored elements |
| Brand subtle | `--color-brand-subtle` | `rgba(240, 124, 30, 0.08)` | Very faint background tints |
| Brand ring | `--color-brand-ring` | `rgba(240, 124, 30, 0.12)` | Focus ring shadows, outline glows |
| Brand glow | `--color-brand-glow` | `rgba(240, 124, 30, 0.18)` | Card hover glow, active shadows |
| Brand ghost | `--color-brand-ghost` | `rgba(240, 124, 30, 0.06)` | Extremely subtle background hints |

### Backgrounds

| Token | CSS Variable | Dark Value | Light Value | Usage |
|---|---|---|---|---|
| App background | `--color-background` | `#0A0A0A` | `#F0EAD6` | Page/shell background |
| Surface | `--color-surface` | `#111111` | `#FFFFFF` | Cards, panels, modals, sidebar |
| Elevated surface | `--color-surface-elevated` | `#1A1A1A` | `#F5F0E8` | Nested panels, hover states, active rows |
| Surface flat | `--color-surface-flat` | `rgba(255,255,255,0.02)` | — | Very subtle surface differentiation |
| Overlay | `--color-overlay` | `rgba(10,10,10,0.85)` | `rgba(0,0,0,0.5)` | Modal backdrop, lightbox |
| Navbar BG | `--color-navbar-bg` | `rgba(10,10,10,0.92)` | `rgba(240,234,214,0.92)` | Top bar with blur |

### Text

| Token | CSS Variable | Dark Value | Light Value | Usage |
|---|---|---|---|---|
| Primary text | `--color-text-primary` | `#F0EAD6` | `#0A0A0A` | Headings, important content |
| Secondary text | `--color-text-secondary` | `#666666` | `#555555` | Body text, descriptions, metadata |
| Accent text | `--color-brand` | `#F07C1E` | `#F07C1E` | Links, section labels, CTAs |
| Text on brand | `--color-text-on-brand` | `#0A0A0A` | `#0A0A0A` | Text placed on orange backgrounds |

### Borders

| Token | CSS Variable | Dark Value | Light Value | Usage |
|---|---|---|---|---|
| Border default | `--color-border` | `#222222` | `#DDDDDD` | Card borders, dividers, table rows |
| Border accent | `--color-border-brand` | `#F07C1E` | `#F07C1E` | Active states, featured items, focus |

### Status / Semantic Colors

| Token | CSS Variable | Value | Usage |
|---|---|---|---|
| Success | `--color-success` | `#7BC67B` | Online, healthy, operational |
| Warning | `--color-warning` | `#F4B266` | Degraded, pending, reconnecting |
| Error | `--color-error` | `#F28F6C` | Failed, validation error, rejected |
| Urgent | `--color-urgent` | `#FF3333` | Critical, break-glass, destructive |
| Info | `--color-info` | `#7AA6FF` | Informational badges (use sparingly) |

### Shadows

| Token | CSS Variable | Value |
|---|---|---|
| Card shadow | `--shadow-card` | `4px 4px 0 var(--color-brand)` |
| Card subtle | `--shadow-card-subtle` | `4px 4px 0 rgba(240, 124, 30, 0.18)` |
| Modal | `--shadow-modal` | `0 20px 40px rgba(0, 0, 0, 0.6)` |
| Focus | `--shadow-focus` | `0 0 0 3px rgba(240, 124, 30, 0.12)` |

### Border Radius

| Token | Value | Guidance |
|---|---|---|
| Default | `0` | Cards, panels, buttons, inputs |
| Small exception | `2px` | Acceptable on small badges or pills |
| Circle | `50%` | Avatars only |

> **Rule**: Do NOT use `rounded-lg`, `rounded-xl`, `rounded-2xl`, or any Tailwind rounding classes on cards, modals, inputs, or buttons. The design language is hard-edged and rectangular.

---

## What MUST Change — Current vs. Target

The current frontend uses Tailwind's `slate-*` color scale (blue-tinted blacks) and some leftover cyan accent values. Here is the complete migration map:

### Background Migration

| Element | ❌ Current (slate-tinted) | ✅ Target (pure dark) |
|---|---|---|
| App shell BG | `bg-slate-950` / `#020617` | `#0A0A0A` |
| Secondary BG | `bg-slate-900` / `#0f172a` | `#111111` |
| Tertiary BG | `bg-slate-800` / `#1e293b` | `#1A1A1A` |
| Card BG | `rgba(15, 23, 42, 0.9)` | `#111111` |
| Card hover BG | `rgba(30, 41, 59, 0.9)` | `#1A1A1A` |
| Input BG | `rgba(30, 41, 59, 0.5)` | `#111111` or `#1A1A1A` |
| Sidebar BG | `bg-slate-950` / `#020617` | `#0A0A0A` |

### Accent Color Migration

| Element | ❌ Current | ✅ Target |
|---|---|---|
| CSS `--color-accent` | `#06b6d4` (CYAN) | `#F07C1E` (ORANGE) |
| CSS `--color-accent-hover` | `#22d3ee` / `#0891b2` | `#C45E0A` |
| Tailwind class | `orange-500` (`#f97316`) | Use custom `brand` color `#F07C1E` |
| Sidebar active | `rgba(6, 182, 212, 0.2)` | `rgba(240, 124, 30, 0.12)` |
| Primary gradient | `from-orange-500 to-amber-600` | Flat `#F07C1E` — no gradients |

### Text Color Migration

| Element | ❌ Current (blue-gray) | ✅ Target (neutral) |
|---|---|---|
| Primary text | `#f1f5f9` (slate-100) | `#F0EAD6` (warm cream) |
| Secondary text | `#94a3b8` (slate-400) | `#666666` (neutral gray) |
| Muted text | `#64748b` (slate-500) | `#666666` (same neutral gray) |

### Border Migration

| Element | ❌ Current | ✅ Target |
|---|---|---|
| Default border | `rgba(51, 65, 85, 0.5)` | `#222222` |
| Subtle border | `rgba(51, 65, 85, 0.3)` | `#222222` |
| Focus border | `rgba(249, 115, 22, 0.5)` | `rgba(240, 124, 30, 0.12)` |

### Border Radius Migration

| Element | ❌ Current | ✅ Target |
|---|---|---|
| Cards | `rounded-lg` (8px) / `rounded-xl` (12px) | `rounded-none` (0) |
| Modals | `rounded-2xl` (16px) | `rounded-none` (0) |
| Buttons | `rounded-md` (6px) / `rounded-lg` (8px) | `rounded-none` (0) |
| Inputs | `rounded-md` (6px) | `rounded-none` (0) |
| Badges | `rounded-full` (9999px) | `rounded-none` or `rounded-sm` (2px) |

---

## CSS Variables — Target `index.css`

Replace the current `:root` and `.dark` blocks in `apps/web/src/index.css` with:

```css
@import "tailwindcss";

/* ── Theme Variables — BSIT 2-2 Color Philosophy ── */
:root {
  /* Fonts */
  --font-sans: 'Inter', system-ui, -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', ui-monospace, monospace;

  /* Brand */
  --color-brand: #F07C1E;
  --color-brand-hover: #C45E0A;
  --color-brand-subtle: rgba(240, 124, 30, 0.08);
  --color-brand-ring: rgba(240, 124, 30, 0.12);
  --color-brand-glow: rgba(240, 124, 30, 0.18);

  /* Light mode backgrounds */
  --color-bg-primary: #F0EAD6;
  --color-bg-secondary: #FFFFFF;
  --color-bg-tertiary: #F5F0E8;
  --color-bg-card: #FFFFFF;
  --color-bg-card-hover: #F5F0E8;
  --color-bg-input: #F5F0E8;
  --color-bg-overlay: rgba(0, 0, 0, 0.5);

  /* Light mode borders */
  --color-border: #DDDDDD;
  --color-border-subtle: #E8E2D4;
  --color-border-brand: #F07C1E;

  /* Light mode text */
  --color-text-primary: #0A0A0A;
  --color-text-secondary: #555555;
  --color-text-tertiary: #777777;
  --color-text-inverse: #F0EAD6;

  /* Light mode accent */
  --color-accent: #F07C1E;
  --color-accent-hover: #C45E0A;
  --color-accent-subtle: rgba(240, 124, 30, 0.08);

  /* Light mode sidebar */
  --color-sidebar-bg: #0A0A0A;
  --color-sidebar-text: #F0EAD6;
  --color-sidebar-active: rgba(240, 124, 30, 0.12);

  /* Status */
  --color-success: #7BC67B;
  --color-warning: #F4B266;
  --color-error: #F28F6C;
  --color-urgent: #FF3333;
  --color-info: #7AA6FF;

  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.2);
  --shadow-md: 0 4px 8px rgba(0, 0, 0, 0.3);
  --shadow-lg: 0 10px 25px rgba(0, 0, 0, 0.4);
  --shadow-glow: 0 0 20px rgba(240, 124, 30, 0.18);
  --shadow-focus: 0 0 0 3px rgba(240, 124, 30, 0.12);
  --shadow-card: 0 4px 16px rgba(0, 0, 0, 0.2);

  /* Transitions */
  --transition-fast: 150ms ease;
  --transition-normal: 250ms ease;
  --transition-slow: 400ms ease;

  /* Layout */
  --sidebar-width: 240px;
  --sidebar-collapsed: 64px;
  --header-height: 56px;
}

.dark {
  /* Dark mode backgrounds — PURE blacks/grays, NO blue tint */
  --color-bg-primary: #0A0A0A;
  --color-bg-secondary: #111111;
  --color-bg-tertiary: #1A1A1A;
  --color-bg-card: #111111;
  --color-bg-card-hover: #1A1A1A;
  --color-bg-input: #111111;
  --color-bg-overlay: rgba(10, 10, 10, 0.85);

  /* Dark mode borders — solid dark grays, NOT transparent whites */
  --color-border: #222222;
  --color-border-subtle: #1A1A1A;
  --color-border-brand: #F07C1E;

  /* Dark mode text — warm cream primary, neutral gray secondary */
  --color-text-primary: #F0EAD6;
  --color-text-secondary: #666666;
  --color-text-tertiary: #666666;
  --color-text-inverse: #0A0A0A;

  /* Dark mode accent — orange, NOT cyan */
  --color-accent: #F07C1E;
  --color-accent-hover: #C45E0A;
  --color-accent-subtle: rgba(240, 124, 30, 0.12);

  /* Dark mode sidebar */
  --color-sidebar-bg: #0A0A0A;
  --color-sidebar-text: #F0EAD6;
  --color-sidebar-active: rgba(240, 124, 30, 0.12);

  /* Dark mode shadows */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.4);
  --shadow-md: 0 4px 8px rgba(0, 0, 0, 0.5);
  --shadow-lg: 0 10px 25px rgba(0, 0, 0, 0.6);
  --shadow-glow: 0 0 20px rgba(240, 124, 30, 0.18);
  --shadow-card: 0 4px 16px rgba(0, 0, 0, 0.4);
}
```

---

## Tailwind Custom Colors

Since Panoptix uses Tailwind CSS v4 with the Vite plugin (no config file), you need to define custom colors using CSS `@theme` or inline CSS variables that Tailwind picks up. Where components use Tailwind utility classes directly, replace Tailwind's default `orange-*` and `slate-*` with the tokens above.

### Inline Tailwind Mapping (Search & Replace)

| ❌ Find this Tailwind class | ✅ Replace with |
|---|---|
| `bg-slate-950` | `bg-[#0A0A0A]` |
| `bg-slate-900` | `bg-[#111111]` |
| `bg-slate-800` | `bg-[#1A1A1A]` |
| `bg-slate-800/50` | `bg-[#1A1A1A]/50` |
| `text-slate-100` | `text-[#F0EAD6]` |
| `text-slate-400` | `text-[#666666]` |
| `text-slate-500` | `text-[#666666]` |
| `border-slate-700` | `border-[#222222]` |
| `border-slate-700/50` | `border-[#222222]` |
| `border-slate-800` | `border-[#222222]` |
| `from-orange-500` | `from-[#F07C1E]` |
| `to-amber-600` | Drop the gradient — use flat `bg-[#F07C1E]` |
| `text-orange-400` | `text-[#F07C1E]` |
| `text-orange-500` | `text-[#F07C1E]` |
| `bg-orange-500/20` | `bg-[rgba(240,124,30,0.12)]` |
| `ring-orange-500/50` | `ring-[rgba(240,124,30,0.12)]` |
| `shadow-orange-500/10` | `shadow-[rgba(240,124,30,0.18)]` |
| `rounded-lg` | `rounded-none` |
| `rounded-xl` | `rounded-none` |
| `rounded-2xl` | `rounded-none` |
| `rounded-md` | `rounded-none` |

---

## Typography

### Font Stack

| Role | Font | Fallback |
|---|---|---|
| Body / UI | Inter | system-ui, sans-serif |
| Monospace | JetBrains Mono | ui-monospace, monospace |

> **Note**: The BSIT 2-2 site uses `Bebas Neue` (display) and `DM Sans` (body). For Panoptix, `Inter` is the correct body/UI font because we need excellent legibility at small sizes in dense dashboard layouts. The display font is not used because Panoptix avoids large hero headings.

### Typography Rules

- Page titles: `1.5rem` to `2rem`, `Inter`, `font-semibold`.
- Card titles: `0.875rem` to `1rem`, `Inter`, `font-medium`.
- Body text: `0.875rem`, `Inter`, regular weight.
- Labels/metadata: `0.75rem`, `JetBrains Mono`, uppercase, `letter-spacing: 0.1em`.
- IDs/timestamps: `0.75rem` to `0.8125rem`, `JetBrains Mono`, no uppercase.
- Do NOT use display fonts for dashboard elements.
- Use uppercase sparingly — only for small labels and status badges.

---

## Design Direction

Panoptix should feel like a serious control plane:

- Dense enough for repeated admin use.
- Calm enough for long monitoring sessions.
- Sharp and technical, not rounded and decorative.
- High contrast, but not noisy.
- Security and audit states must be visually obvious.

Use the BSIT 2-2 identity as the visual foundation:

- sharp geometry;
- monochrome dark surfaces;
- one primary accent color;
- strong typography roles;
- restrained motion;
- hard, rectangular UI surfaces.

Do not apply the landing-page parts of the BSIT system directly. Panoptix should not use huge hero titles, cinematic scroll reveals, decorative film grain over dashboards, or grayscale image hover effects for operational screens.

---

## Component Guidance

### Sidebar Navigation

- Background: `#0A0A0A` (same as app shell).
- Active item: orange text `#F07C1E` + subtle background `rgba(240, 124, 30, 0.12)`.
- Inactive items: `#666666` text, hover to `#F0EAD6`.
- Active indicator dot/line: solid `#F07C1E`.
- No gradient backgrounds on active items.
- Sharp edges, no rounded hover states.

### Stat Cards (Dashboard)

- Background: `#111111`, border: `1px solid #222222`.
- Top accent line: `3px solid #F07C1E` for all cards (single accent — no multi-color tops).
- Icon background: `rgba(240, 124, 30, 0.08)`.
- Number text: `#F0EAD6`, label text: `#666666`.
- No colored tops using `--success`, `--info`, or `--warning` — only `#F07C1E`.

### Cards and Panels

- Background: `#111111`.
- Border: `1px solid #222222`.
- Border-radius: `0`.
- Hover: background `#1A1A1A`, optional `box-shadow: 0 0 20px rgba(240, 124, 30, 0.18)`.
- No rounded SaaS-style cards. No nested cards inside cards.

### Buttons

- Primary: `background: #F07C1E`, `color: #0A0A0A`, hover `background: #C45E0A`.
- Secondary: `background: transparent`, `border: 1px solid #222222`, `color: #666666`, hover `border-color: #F07C1E`, `color: #F07C1E`.
- Destructive: `border: 1px solid #FF3333`, `color: #FF3333`, always with confirmation dialog.
- Border-radius: `0` on all buttons.
- No gradient fills.

### Tables

- Header: `#666666` text, uppercase, `0.75rem`, `JetBrains Mono`, `letter-spacing: 0.1em`.
- Row background: `#111111`, alternating `#0A0A0A`.
- Row border: `1px solid #222222`.
- Row hover: `#1A1A1A`.
- Selected/active row: `rgba(240, 124, 30, 0.08)` background.

### Forms and Inputs

- Input background: `#111111`.
- Input border: `1px solid #222222`.
- Focus border: `1px solid #F07C1E` + `box-shadow: 0 0 0 3px rgba(240, 124, 30, 0.12)`.
- Label: `#666666`, uppercase mono, `0.75rem`.
- Error border: `1px solid #F28F6C`.
- Border-radius: `0`.

### Modals and Drawers

- Background: `#111111`.
- Border: `1px solid #222222`.
- Overlay: `rgba(10, 10, 10, 0.85)` with `backdrop-filter: blur(4px)`.
- Shadow: `0 20px 40px rgba(0, 0, 0, 0.6)`.
- Border-radius: `0`.
- Title text: `#F07C1E`, mono, uppercase.

### Badges and Status Pills

- Background: use status color at low opacity (`rgba(color, 0.1)`).
- Text: use status color.
- Border-radius: `0` or `2px`.
- Keep text uppercase, short label.

### Camera and Video Surfaces

- Clean, inspectable video surfaces.
- No grayscale filters, film grain, heavy blur, or decorative overlays on live video.
- Control overlays use `rgba(10, 10, 10, 0.7)` background.

### Scrollbar

- Track: `transparent` or `#0A0A0A`.
- Thumb: `#F07C1E` (brand color).
- Width: `6px` to `8px`.

---

## What NOT to Do

| ❌ Don't | ✅ Instead |
|---|---|
| Use `bg-slate-*` Tailwind classes | Use pure dark tokens `#0A0A0A`, `#111111`, `#1A1A1A` |
| Use cyan anywhere (`#06b6d4`) | Use orange `#F07C1E` |
| Use `from-X to-Y` gradient accents | Use flat `#F07C1E` everywhere |
| Use `rounded-lg` / `rounded-xl` on cards | Use `rounded-none` |
| Multi-color stat card tops | All stat cards use `#F07C1E` top border |
| Blue-gray text (`#94a3b8`, `#64748b`) | Neutral gray `#666666` |
| `rgba(255,255,255,0.06)` borders | Solid `#222222` borders |
| Decorative gradients as backgrounds | Flat dark surfaces |
| Large hero sections in admin pages | Compact section headers |
| Slow scroll-reveal animations | Short `150ms–200ms` transitions |

---

## Migration Approach

Do not rewrite the whole frontend in one pass.

Recommended order:

1. **Update `index.css` CSS variables** — Replace all `:root` and `.dark` blocks with the target values above.
2. **Align new pages** to this guide first.
3. **Refactor shared component patterns** — buttons, cards, inputs, tables, badges, modals.
4. **Migrate high-impact screens** — dashboard, camera modal, audit, users, gateways.
5. **Remove old patterns** — Search for all `slate-*`, `cyan-*`, `rounded-lg`, `rounded-xl`, `rounded-2xl` Tailwind classes and replace per the mapping table.

Each migration step must keep the app functional and pass:

```powershell
npm run lint
npm run build
```

---

## Acceptance Checklist

Before a new frontend screen is considered aligned with this design system:

- [ ] Uses orange `#F07C1E` as the primary accent, NOT cyan and NOT Tailwind's `orange-500`.
- [ ] Background colors are pure dark (`#0A0A0A`, `#111111`, `#1A1A1A`), NOT slate-tinted.
- [ ] Text colors are warm cream `#F0EAD6` (primary) and neutral gray `#666666` (secondary), NOT blue-gray slate.
- [ ] Borders use solid `#222222`, NOT transparent white overlays.
- [ ] All cards, buttons, inputs, and modals have `border-radius: 0`.
- [ ] No gradient accents — flat orange only.
- [ ] Stat cards use single-color orange top border, not multi-color.
- [ ] Uses dark-first dashboard density.
- [ ] Shows loading, empty, denied, degraded, and error states separately.
- [ ] Keeps dangerous admin actions behind confirmation.
- [ ] Does not expose secrets or gateway-only capabilities.
- [ ] Works in both dark and light mode if the screen supports theme switching.

---

## Quick Visual Reference

### Dark Mode Palette

```
┌──────────────────────────────────────────────────┐
│  #0A0A0A  ██████  App background / Shell         │
│  #111111  ██████  Cards / Panels / Surfaces       │
│  #1A1A1A  ██████  Elevated / Hover / Active rows  │
│  #222222  ██████  Borders / Dividers              │
│  #666666  ██████  Secondary text / Muted           │
│  #F0EAD6  ██████  Primary text (warm cream)        │
│  #F07C1E  ██████  Brand accent (warm orange)       │
│  #C45E0A  ██████  Brand hover (dark orange)        │
│  #7BC67B  ██████  Success (green)                  │
│  #F4B266  ██████  Warning (amber)                  │
│  #F28F6C  ██████  Error (salmon)                   │
│  #FF3333  ██████  Urgent (red)                     │
│  #7AA6FF  ██████  Info (blue) — use sparingly      │
└──────────────────────────────────────────────────┘
```

### Light Mode Palette

```
┌──────────────────────────────────────────────────┐
│  #F0EAD6  ██████  App background (warm cream)     │
│  #FFFFFF  ██████  Cards / Panels / Surfaces       │
│  #F5F0E8  ██████  Elevated / Hover                │
│  #DDDDDD  ██████  Borders / Dividers              │
│  #555555  ██████  Secondary text                   │
│  #0A0A0A  ██████  Primary text                     │
│  #F07C1E  ██████  Brand accent (same orange)       │
│  #C45E0A  ██████  Brand hover (same dark orange)   │
└──────────────────────────────────────────────────┘
```
