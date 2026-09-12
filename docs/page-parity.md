# Frontend page and workflow parity

Inventory date: 2026-09-12. The current App Router contains 162 `page.tsx` or
`route.ts` files. The route tree was compared with the historical trees from
the domain milestones and app-shell consolidation commits. No historical page
file is absent from the current source tree. The parity risk is discoverability:
the unified shell may merge navigation groups while preserving canonical URLs.

## Status vocabulary

`PRESENT` is a live canonical route. `MERGED` is a workflow available through a
different canonical surface. `REDIRECTED` is an old URL that resolves to a
canonical route. `INTENTIONALLY_REPLACED` is an approved product change.
`MISSING` requires restoration. `DEFERRED_MOBILE` means web parity is present
but native support is intentionally pending.

## Parity matrix

The route column is the complete current route family inventory; dynamic
segments are shown literally. Every route remains backed by its existing API
and domain service. Desktop, tablet, mobile web, and PWA use the same web route;
native status is tracked in `docs/mobile-parity.md`.

| Route / feature | Previous route | Current route | Status | Desktop | Tablet | Mobile Web | PWA | Native Mobile | Notes |
|---|---|---|---|---|---|---|---|---|---|
| Dashboard / home | `/`, `/dashboard` | `/dashboard` | MERGED | PRESENT | PRESENT | PRESENT | PRESENT | READ/OPERATE | `/` remains the entry point |
| My Work, Inbox, Copilot | new M26 surfaces | `/my-work`, `/inbox`, `/copilot` | PRESENT | PRESENT | PRESENT | PRESENT | PRESENT | READ/OPERATE | backend-derived projections |
| Approvals, Boards, Automations | new M26/M27 surfaces | `/approvals`, `/workspace/boards`, `/workspace/automations` | PRESENT | PRESENT | PRESENT | PRESENT | PRESENT | READ/OPERATE | domain authorization remains authoritative |
| Workspace overview, tasks, notifications, activity | `/workspace/...` | `/workspace`, `/workspace/tasks`, `/workspace/notifications`, `/workspace/activity` | PRESENT | PRESENT | PRESENT | PRESENT | READ/OPERATE | actions remain API-backed |
| Workspace artists | `/workspace/artists...` | `/workspace/artists`, `/workspace/artists/new`, `/workspace/artists/[id]` | PRESENT | PRESENT | PRESENT | PRESENT | READ/OPERATE | artist 360 detail is preserved |
| Booking Show Day | new completion surface | `/workspace/bookings/[id]/show-day` | PRESENT | PRESENT | PRESENT | PRESENT | PRESENT | DEFERRED_MOBILE | show-day operational view over Booking data |
| Bookings and call sheets | `/workspace/bookings...` | `/workspace/bookings`, `/workspace/bookings/new`, `/workspace/bookings/[id]`, `/workspace/bookings/[id]/call-sheet`, `/workspace/call-sheets/...` | PRESENT | PRESENT | PRESENT | PRESENT | READ/OPERATE | generation and published views retained |
| Production and travel | `/workspace/production...`, `/workspace/travel...` | existing workspace list/detail/edit/new routes | PRESENT | PRESENT | PRESENT | PRESENT | READ/OPERATE | operational data only on mobile |
| Promoters, venues, contacts | `/workspace/{promoters,venues,contacts}...` | existing workspace list/detail/edit/new routes | PRESENT | PRESENT | PRESENT | PRESENT | READ/OPERATE | scoped selectors and relationships retained |
| Campaigns and rollouts | `/workspace/campaigns...`, `/workspace/rollouts...` | existing workspace routes | PRESENT | PRESENT | PRESENT | PRESENT | READ/OPERATE | task-oriented rollout workflow |
| Music Workspace / Metadata / Distribution | new completion surfaces | `/workspace/music`, `/workspace/music/metadata`, `/workspace/music/distribution` | PRESENT | PRESENT | PRESENT | PRESENT | PRESENT | DEFERRED_MOBILE | conservative catalog/readiness views over existing APIs |
| Releases, tracks, music | `/workspace/music...` | existing workspace music routes | PRESENT | PRESENT | PRESENT | PRESENT | READ/OPERATE | no fabricated analytics |
| Contracts | `/workspace/contracts...` | existing list/new/detail/edit/print routes | PRESENT | PRESENT | PRESENT | PRESENT | READ/OPERATE | approval actions use contract service |
| Documents | `/workspace/documents...` | existing list/new/detail routes | PRESENT | PRESENT | PRESENT | PRESENT | READ ONLY | mobile metadata/authorized download only |
| Finance, invoices, payments | `/workspace/finance...` | existing finance list/detail/new/print routes | PRESENT | PRESENT | PRESENT | PRESENT | READ ONLY | conservative native boundary |
| Rights and royalties | `/workspace/rights...`, `/workspace/royalties...` | existing workspace routes | PRESENT | PRESENT | PRESENT | PRESENT | READ ONLY | no ownership/finalization mutation |
| Reports and templates | `/workspace/reports...`, `/workspace/settings/templates` | existing workspace routes | PRESENT | PRESENT | PRESENT | PRESENT | WEB ONLY FOR NOW | saved-view architecture retained |
| Organization, team, invitations, branding, domains | existing workspace settings routes | existing routes | PRESENT | PRESENT | PRESENT | PRESENT | WEB ONLY FOR NOW | administration is not mobile-first |
| Calendar | `/workspace/calendar` | `/workspace/calendar` | PRESENT | PRESENT | PRESENT | PRESENT | READ/OPERATE | native calendar shell included |
| Artist portal | `/artist/...` | existing artist routes | PRESENT | PRESENT | PRESENT | PRESENT | READ ONLY | explicit artist links still required |
| Platform administration | `/platform/...` | existing platform routes | PRESENT | PRESENT | PRESENT | PRESENT | WEB ONLY FOR NOW | superuser-only capability context |
| Developer and integration settings | `/developer/...`, `/platform/connectors/...` | existing routes | PRESENT | PRESENT | PRESENT | PRESENT | WEB ONLY FOR NOW | secrets are never displayed |
| Profile, security, channels | `/profile/...` | existing profile routes | PRESENT | PRESENT | PRESENT | PRESENT | READ/OPERATE | channel connection is permission/config gated |
| Authentication and offline | `/login`, `/reauthenticate`, `/invite/[token]`, `/offline` | same canonical routes | PRESENT | PRESENT | PRESENT | PRESENT | DEFERRED_MOBILE | native auth awaits security decision |

## Historical review and redirects

The historical page trees were reviewed through Git history for `frontend/app`
and `frontend/components/app-shell.tsx`. No source route requires restoration
at this checkpoint. `/` and `/dashboard` are the intentional dashboard
consolidation; platform remains a superuser context rather than a duplicate
workspace. Existing deep links are preserved. No redirect was added because
there is no unambiguous retired URL that is currently missing from the router.

## Action parity

Create, edit, assign, lifecycle, archive/cancel, complete, generate, publish,
upload/download, approve/reject, comment/mention, and export remain governed by
the existing action manifest and Django services. Route regression checks now
assert the high-value canonical destinations and prevent a future shell change
from silently removing them.
