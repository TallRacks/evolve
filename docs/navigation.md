# Navigation and product consolidation

The application shell separates tenant workspace, Artist portal, and platform administration. Navigation groups are permission-aware UX; Django remains authoritative for every destination and API.

Workspace groups cover Overview, Artists, Live & Operations, Music, Rights & Royalties, Finance, Content & Records, Organization, and Account. Platform superusers receive a separate cross-organization structure. Artist-linked users receive only the limited Artist portal structure.

Groups are keyboard-operable and collapsible. Collapse preferences may be stored in browser local storage because they are presentation preferences only. Organization choice remains UX context and never grants access.

`Cmd+K` or `Ctrl+K` opens the command palette. It combines visible navigation commands with backend-authorized Global Search. Arrow keys select results, Enter opens one, and Escape closes the dialog.

## Travel integration

See `docs/travel.md` for the implemented Travel integration and its authorization, privacy, and snapshot rules.

## Production

Production is a canonical item in the Live & Operations group, with a permission-aware create command. Platform and Artist navigation expose their respective superuser and curated read-only routes.


## Contracts

Contracts appears under Content & records in the workspace and platform navigation, and as an executed-only Artist portal destination. Visibility mirrors backend permission state for usability only; Django remains authoritative. Existing URLs remain stable.
