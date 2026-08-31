# PWA and Mobile

## Product model

Mobile web is a responsive browser fallback. Installed Evolve is a purpose-designed application mode, not merely the website without browser chrome.

## Implemented foundation

- Next.js-generated installable manifest with Evolve identity, standalone display, theme, icon, scope, start URL, and shortcuts.
- Generated 512px Evolve app icon suitable for regular and maskable use.
- Production-only service-worker registration.
- Permission-filtered installed-mobile bottom navigation plus More.
- Safe-area-aware top and bottom layout using CSS environment insets.
- 44px minimum shared form/button targets and 16px mobile fields.
- Explicit offline, reconnect, and update-ready states.
- Deep links preserve existing application routes and browser/app back behavior.

## Security and offline policy

Operational and authenticated content is network-only. The worker ignores `/api/*` and `/admin/*` and does not cache authenticated HTML navigation. Offline mode shows a static failure screen and disables the expectation of mutation. No private data is claimed to be available offline.

## Breakpoint behavior

- Desktop: persistent sidebar, wide content, multi-column operational views.
- Tablet: drawer navigation and reduced column density through existing responsive grids.
- Mobile web: drawer-based fallback with stacked forms and content.
- Installed mobile below 48rem: standalone top bar, bottom navigation, safe areas, and additional content clearance.

## Deferred capabilities

Push delivery, app badges, background sync, offline mutations, camera-specific workflows, and OS share targets are not claimed. They require explicit security, permission, and delivery designs.
