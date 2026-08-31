# Evolve Design System

## Product character

Evolve is restrained, operational, editorial, and information-rich. Hierarchy comes from typography, spacing, alignment, borders, and state rather than decorative cards or gradients.

## Application shell

Desktop uses a persistent 17-18rem sidebar, grouped permission-aware navigation, a sticky command/search bar, organization context, notifications, and profile access. Tablet and mobile web use the same authorized navigation through a drawer. Installed mobile adds a safe-area-aware bottom navigation for high-frequency destinations plus More.

Frontend navigation is presentation only. Django authorizes every request.

## Typography

- UI: Geist with system sans-serif fallback.
- Display headings: Manrope with UI fallback.
- Page titles: 24px mobile, 30px from small desktop widths.
- Body and operational data: 14-16px.
- Labels and eyebrows: 12px, semibold, uppercase where hierarchy benefits.

## Layout and density

- Content maximum: 90rem.
- Top bar: 4rem plus device safe area in installed mode.
- Form controls and primary buttons: minimum 44px touch height.
- Radius: 6px for controls and framed operational items.
- Desktop tables remain dense; mobile treatments prioritize essential fields and detail navigation.

## Semantic tokens

`--background`, `--surface`, `--surface-raised`, `--surface-hover`, `--text-primary`, `--text-secondary`, `--text-muted`, `--border`, `--border-strong`, `--accent`, `--accent-strong`, `--success`, `--warning`, `--danger`, and `--info` are defined in `frontend/app/globals.css`.

## States

Loading, empty, error, positive, warning, offline, reconnect, and update states use shared visual language. Status must never rely on color alone. Destructive actions require explicit confirmation where implemented.

## Command-centre surfaces

Operational pages use compact bordered bands, tabular KPI numbers, semantic status text, restrained default-theme amber accents, and dense rows on desktop. Tablet grids reduce columns; mobile rows stack without requiring horizontal tables. Organization branding tokens remain authoritative and no tenant-specific color is hard-coded into data or authorization.
