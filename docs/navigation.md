# Navigation and product consolidation

The application uses one authenticated shell and canonical Dashboard. Platform administration is a superuser-only capability/context within that shell; the Artist portal remains a deliberately limited experience. Navigation groups are permission-aware UX; Django remains authoritative for every destination and API.

Workspace groups cover Overview, Artists, Live & Operations, Music, Finance with nested Rights/Royalties, Content & Records, Organization, and Account. Platform superusers receive an additional Platform capability group without duplicate primary domain destinations. Artist-linked users receive only the limited Artist portal structure.

Groups are keyboard-operable and collapsible. Collapse preferences may be stored in browser local storage because they are presentation preferences only. Organization choice remains UX context and never grants access.

`Cmd+K` or `Ctrl+K` opens the command palette. It combines visible navigation commands with backend-authorized Global Search. Arrow keys select results, Enter opens one, and Escape closes the dialog.

## Travel integration

See `docs/travel.md` for the implemented Travel integration and its authorization, privacy, and snapshot rules.

## Production

Production is a canonical item in the Live & Operations group, with a permission-aware create command. Platform and Artist navigation expose their respective superuser and curated read-only routes.


## Contracts

Contracts appears under Content & records in the workspace and platform navigation, and as an executed-only Artist portal destination. Visibility mirrors backend permission state for usability only; Django remains authoritative. Existing URLs remain stable.

## Workflow destinations

The workspace shell includes `/workspace/tasks`, `/workspace/notifications`, `/workspace/activity`, and `/workspace/settings/templates`; Account Security is `/profile/security`. Password freshness failures use `/reauthenticate`. Existing domain URLs and deep links remain unchanged.

## Unified shell

The authenticated application uses one `AppShell` and one canonical `/dashboard`. Platform is a
superuser-only context and capability group, not a duplicate application. The context selector stores
only `platform` or an allowed organization UUID in session storage for presentation; Django validates
every request and no membership is created or changed by switching context. Existing `/platform/...`
deep links remain stable, while `/platform` redirects to the canonical Dashboard.

In Platform context organization workflows are hidden and platform configuration/governance is shown.
In organization context the same shell applies organization branding and permission-aware workflows;
platform superusers additionally retain the Platform group. `is_staff` has no platform capability.

## Web/native parity rule

The web App Router is regression-checked by `npm run test:routes`. Native navigation is operational: Home, My Work, Create, Inbox, and More are Expo Router tabs; administrative Platform/Developer destinations remain web-first. Every new feature must account for Desktop, Tablet, Mobile Web, installed PWA, native iOS, Android implications, and shared API impact.

- Platform → Google Workspace is the canonical, configuration-gated entry point for Google-native document foundations.
- Music → Metadata and Music → Distribution are operational views over existing catalog APIs.
- Booking detail exposes the deterministic Next Best Action and Show Day view.
