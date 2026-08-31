# Evolve Components

## Shared shell

`AppShell` owns grouped navigation, command/search, organization selection, notification access, profile access, mobile drawer behavior, and installed-app bottom navigation. `RouteGuard` prevents protected content from rendering before session resolution but is not an authorization control.

## Shared page primitives

`frontend/components/ui/page.tsx` provides `PageHeader`, `StatCard`, `EmptyState`, `StatusBadge`, `LoadingState`, `ErrorState`, `SectionHeader`, `Breadcrumbs`, and shared field/button classes.

`ActionDialog` supplies confirmation for consequential actions. Domain page modules compose these primitives and call same-origin APIs through the shared client.

## Product modules

Page-level components are grouped by established domain: management, artists, bookings, call sheets, campaigns, calendar/documents, contracts, finance, integrations, music, notifications, production, relationships, reporting, rights, travel, white-label, and workflows.

## Rules

- Reuse primitives before introducing a parallel pattern.
- Keep authorization and business rules in Django.
- Provide loading, empty, error, and permission-denied states.
- Use Lucide icons for recognizable commands.
- Keep buttons functional and permission-aware.
