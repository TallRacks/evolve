# Evolve Style Sheet

The implemented source of truth is `frontend/app/globals.css` plus shared Tailwind class constants in `frontend/components/ui/page.tsx`.

| Token or measure | Implemented value |
| --- | --- |
| Background | `#0b0d0e` |
| Surface | `#121516` |
| Raised surface | `#191d1f` |
| Primary text | `#f4f1e9` |
| Muted text | `#858a87` |
| Accent | `#d4ad55` |
| Accent strong | `#f0cc73` |
| Success | `#58a981` |
| Danger | `#d66b67` |
| Border | `#292e30` |
| Strong border | `#3a4143` |
| Content width | `90rem` |
| Base radius | `0.375rem` |
| Control minimum height | `2.75rem` |

Breakpoints follow Tailwind defaults for page composition. Installed-PWA behavior has an explicit `display-mode: standalone` query below 48rem. Safe areas use `env(safe-area-inset-*)`.

Avoid negative letter spacing, viewport-scaled type, decorative nested cards, and unconstrained horizontal page overflow.
