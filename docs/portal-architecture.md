# Portal Architecture

The authenticated shell uses a responsive sidebar, organization context, profile access, and
logout. Navigation follows bootstrap permissions for usability, while Django independently
authorizes every API request.

## Routes

- /dashboard: real organization or platform totals
- /workspace: current organization overview
- /workspace/team: member search, filters, roles, and active state
- /workspace/invitations: invitation lifecycle and one-time token generation
- /workspace/organization and /workspace/settings: core settings
- /platform: platform totals
- /platform/organizations/* and /platform/users/*: platform inventories and details
- /platform/audit: read-only mutation history
- /profile: safe name editing and membership display
- /invite/[token]: authenticated invitation acceptance

Shared request code adds same-origin cookies and Django CSRF headers to mutations. Forms use
consistent validation notices, confirmations, disabled states, status badges, and empty
states. Tables and navigation degrade to scrolling or slide-over layouts on narrow screens.

Milestone 6 routes add `/workspace/artists`, `/workspace/artists/new`, and artist detail pages;
platform superusers use `/platform/artists` and its detail pages. `/artist` resolves only explicitly
linked artist profiles authorized by an active artist-role membership, supports multiple linked
profiles, and exposes no organization administration controls.
