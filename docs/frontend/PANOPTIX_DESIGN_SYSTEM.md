# Panoptix Frontend Design System

This guide adapts the BSIT 2-2 design-system extraction for Panoptix. Panoptix is a CCTV dashboard, admin panel, and security operations tool, so use the dashboard/admin adaptation of the visual language instead of the landing-page baseline.

The goal is a dark-first, compact, sharp, operational interface with a warm orange accent and strong scanability.

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

## System Type

Panoptix maps to these design-system categories:

| Area | System type | Design behavior |
|---|---|---|
| Viewer dashboard | Dashboard / admin panel | Dense, clean, scan-first camera grid |
| Admin pages | Form-heavy SaaS tool | Compact forms, clear validation, strong confirmations |
| Audit and actor investigation | Documentation + dashboard hybrid | Tables, filters, timelines, metadata, readable detail panels |
| Gateway and health screens | Operations dashboard | Status-first cards, clear degraded/offline states |
| Login and privacy notice | SaaS entry flow | Focused, minimal, trust-building |

## Token Direction

These are the target visual tokens for future frontend refactors.

| Token role | Value | Usage |
|---|---|---|
| Brand accent | `#F07C1E` | Primary actions, active navigation, focus accents, important labels |
| Brand hover | `#C45E0A` | Hover and pressed states |
| Dark background | `#0A0A0A` | App shell and page background |
| Surface | `#111111` | Cards, panels, modals |
| Elevated surface | `#1A1A1A` | Nested panels, active rows, secondary surfaces |
| Primary text on dark | `#F0EAD6` | Main text and headings |
| Primary text on light | `#0A0A0A` | Light-mode main text |
| Muted text | `#666666` dark, `#555555` light | Metadata, helper copy, inactive labels |
| Border | `#222222` dark, `#DDDDDD` light | Dividers, cards, input borders |
| Success | `#7BC67B` | Healthy, online, allowed |
| Warning | `#F4B266` | Degraded, pending, needs attention |
| Error | `#F28F6C` | Failed validation, command rejection |
| Urgent | `#FF3333` | Critical, break-glass, destructive operations |

Current frontend note: the app still uses a cyan/slate/rounded visual system in many components. Future UI work should gradually migrate toward the orange/dark/sharp system without breaking existing frontend behavior.

## Typography Direction

Use a three-role typography model:

| Role | Recommended use |
|---|---|
| Display font | Major page labels only, not dense cards or table headings |
| Body font | Content, card titles, button labels when readability matters |
| Mono font | IDs, timestamps, filters, badges, audit metadata, camera codes, gateway identifiers |

Rules:

- Avoid landing-page hero scale in the app.
- Use smaller page titles around `1.5rem` to `2rem` for admin screens.
- Use `0.875rem` to `0.95rem` body text in dense panels.
- Use uppercase mono labels for metadata, but keep long values readable.
- Do not use negative letter spacing.

## Dashboard Adaptation Rules

For Panoptix dashboard/admin screens:

- Use compact section padding, around `2rem` vertically.
- Use wide containers, up to `1400px` or full width where data tables need it.
- Use compact card padding, around `1rem` to `1.25rem`.
- Use tighter grid gaps, around `0.75rem`.
- Keep animation short, around `0.15s` to `0.2s`.
- Disable film grain in dashboard and admin views.
- Disable decorative image grayscale effects for camera/video surfaces.
- Prefer a fixed/collapsible sidebar for app navigation.
- Keep default theme dark.

Avoid:

- giant hero sections;
- marketing-style split layouts;
- decorative gradients as primary backgrounds;
- nested cards inside cards;
- oversized rounded corners;
- slow scroll reveal animations in admin pages.

## Component Guidance

### Sidebar Navigation

- Use a dark fixed/collapsible sidebar.
- Active item uses brand orange and a subtle surface highlight.
- Labels should be readable and compact.
- Include system status, but keep it secondary.

### Cards And Panels

- Use sharp rectangles.
- Prefer `1px` borders and flat surfaces.
- Avoid rounded SaaS-style cards.
- Use a subtle hard hover only where useful: `translateY(-2px)` with a small orange offset shadow.
- Do not make every page section look like a floating card; reserve cards for actual grouped content.

### Buttons

- Primary action: orange border or orange fill depending on risk and prominence.
- Secondary action: transparent or surface background with border.
- Destructive action: urgent red, always with confirmation for admin mutations.
- Button labels should be direct, not marketing copy.
- Icon buttons should use lucide icons with accessible labels/tooltips.

### Tables

- Tables are first-class UI for audit, users, gateways, and command history.
- Header labels should use small uppercase mono text.
- Rows need strong hover/focus states and readable density.
- Filters should be visible and compact.
- Empty, denied, loading, degraded, and error states must be visually distinct.

### Forms

- Inputs use dark surfaces, `1px` borders, and orange focus rings.
- Labels use small uppercase mono text.
- Validation errors use clear text plus error border color.
- Long admin forms should be grouped by operational intent, not visual decoration.

### Modals And Drawers

- Use modals for confirmation and destructive actions.
- Use drawers or detail panels for actor profiles, camera details, and gateway details.
- Keep max width practical and content scrollable.
- Never show secrets, RTSP credentials, LiveKit admin credentials, or gateway publish tokens in persistent UI.

### Badges And Status Pills

- Use badges for role, actor type, camera status, command status, audit severity, and outcome.
- Keep badge text uppercase and short.
- Do not use too many accent colors; status colors should carry meaning.

### Camera And Video Surfaces

- Camera/video areas should be clean and inspectable.
- Do not apply grayscale filters, film grain, heavy blur, or decorative overlays to live video.
- Viewer identity watermarking is a future/pilot feature and must not obscure the primary CCTV image.
- Playback controls should be minimal and subscriber-only.

## Panoptix-Specific Rules

- Prioritize scanability over visual drama.
- Treat audit, actor investigation, and gateway command screens as operational tools.
- Security/audit states must be more prominent than decorative branding.
- Do not hide important operational states behind generic loading or error UI.
- Do not use browser camera/microphone/publisher affordances.
- Do not expose RTSP URLs, camera credentials, LiveKit admin secrets, or gateway service tokens.
- Keep same-origin `/api/v1/*` as the browser data path.

## Migration Approach

Do not rewrite the whole frontend in one pass.

Recommended order:

1. Add token names and theme direction in frontend docs.
2. Align new pages to this guide first.
3. Refactor shared primitives gradually: buttons, cards, inputs, tables, badges, modals.
4. Migrate high-impact screens: dashboard, camera modal, audit, users, gateways.
5. Remove old cyan/slate/rounded patterns once equivalent sharp/orange components exist.

Each migration step must keep the app functional and pass:

```powershell
npm run lint
npm run build
```

## Acceptance Checklist

Before a new frontend screen is considered aligned with this design system:

- [ ] Uses orange as the primary accent, not cyan.
- [ ] Uses dark-first dashboard density.
- [ ] Avoids large landing-page hero treatment.
- [ ] Avoids unnecessary rounded cards.
- [ ] Uses clean camera/video surfaces.
- [ ] Shows loading, empty, denied, degraded, and error states separately.
- [ ] Keeps dangerous admin actions behind confirmation.
- [ ] Does not expose secrets or gateway-only capabilities.
- [ ] Works in both dark and light mode if the screen supports theme switching.

