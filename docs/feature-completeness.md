# Web feature completeness audit

This audit is about discoverability and working workflows, not only route
existence. Django APIs and domain services remain authoritative. `PRESENT`
means the canonical web route and at least one real API-backed action are
reachable; `PARTIAL` means the domain exists but an important workflow remains
web-first or needs a later backend contract; `DEFERRED` is intentionally out of
scope.

| Domain | List | Create | Detail | Edit | Lifecycle | Related actions | Search/filter | Mobile Web | PWA | Native API ready |
|---|---|---|---|---|---|---|---|---|---|---|
| Dashboard | PRESENT | PRESENT | PRESENT | n/a | n/a | quick create | PRESENT | PRESENT | PRESENT | PRESENT |
| Artists | PRESENT | PRESENT | PRESENT | PRESENT | archive | team, bookings, music, docs | PRESENT | PRESENT | PRESENT | PRESENT |
| Bookings | PRESENT | PRESENT | PRESENT | PRESENT | status/cancel | operations, call sheet, production, travel | PRESENT | PRESENT | PRESENT | PRESENT |
| Production | PRESENT | PRESENT | PRESENT | PRESENT | status | requirements, checklist, docs | PRESENT | PRESENT | PRESENT | PRESENT |
| Call Sheets | PRESENT | generated | PRESENT | draft-only | publish/cancel | refresh, print, show day | n/a | PRESENT | PRESENT | PRESENT |
| Travel | PRESENT | PRESENT | PRESENT | PRESENT | lifecycle | segments, accommodation, docs | PRESENT | PRESENT | PRESENT | PRESENT |
| Promoters / Venues / Contacts | PRESENT | PRESENT | PRESENT | PRESENT | deactivate/archive | relationships, booking links | PRESENT | PRESENT | PRESENT | PRESENT |
| Releases / Tracks | PRESENT | PRESENT | PRESENT | PRESENT | release/archive | credits, placements, links, tasks, docs | PRESENT | PRESENT | PRESENT | PRESENT |
| Works / Recording / Assets | PARTIAL | DEFERRED | PARTIAL | PARTIAL | DEFERRED | Rights and Documents links | PARTIAL | PARTIAL | PARTIAL | READ ONLY |
| Campaigns / Rollouts | PRESENT | PRESENT | PRESENT | PRESENT | lifecycle | tasks, releases, documents | PRESENT | PRESENT | PRESENT | PRESENT |
| Calendar / Tasks | PRESENT | PRESENT | PRESENT | PRESENT | complete/status | assignments, checklist, context | PRESENT | PRESENT | PRESENT | PRESENT |
| Notifications / Activity | PRESENT | n/a | PRESENT | read/archive | archive/read | deep links, Inbox projection | PRESENT | PRESENT | PRESENT | PRESENT |
| Documents / Contracts | PRESENT | PRESENT | PRESENT | PRESENT | archive/approve/reject | links, templates, print | PRESENT | PRESENT | PRESENT | READ/OPERATE |
| Office | PARTIAL | PRESENT | PRESENT | PRESENT | archive/restore | shared, recent, starred, revisions | PRESENT | PRESENT | PRESENT | READ ONLY |
| Finance / Invoices / Payments | PRESENT | PRESENT | PRESENT | PRESENT | issue/void/allocation | booking and contract context | PRESENT | PRESENT | PRESENT | READ ONLY |
| Rights / Royalties | PRESENT | PRESENT | PRESENT | limited | finalize/immutable | music context | PRESENT | PRESENT | PRESENT | READ ONLY |
| Reports | PRESENT | n/a | PRESENT | filters/views | n/a | CSV export, saved views | PRESENT | PRESENT | PRESENT | WEB FIRST |
| Team / Invitations / Organization | PRESENT | PRESENT | PRESENT | PRESENT | deactivate/revoke | membership, permissions | PRESENT | PRESENT | PRESENT | WEB FIRST |
| Branding / Domains / Developer | PRESENT | PRESENT | PRESENT | PRESENT | activate/verify/revoke | integrations, API docs | PRESENT | PRESENT | PRESENT | WEB FIRST |
| Email / Storage / AI / Channels | PRESENT | PRESENT | PRESENT | PRESENT | activate/deactivate | test/configuration, Copilot | PRESENT | PRESENT | PRESENT | CONFIG-GATED |
| My Work / Inbox / Approvals | PRESENT | n/a | PRESENT | action-specific | complete/approve/reject | mentions, confirmations | PRESENT | PRESENT | PRESENT | PRESENT |
| Boards / Automations | PRESENT | rule-gated | PRESENT | rule/view controls | activate/deactivate | domain transitions, executions | PRESENT | PRESENT | PRESENT | PRESENT |
| Music Workspace | PRESENT | release/track | PRESENT | domain pages | lifecycle | rights, campaign, docs, tasks | PRESENT | PRESENT | PRESENT | PRESENT |
| Workspaces | PRESENT | quick create | PRESENT | n/a | archive | board/list/report grouping, selector | PRESENT | PRESENT | PRESENT | PRESENT |

## Current completion actions

The existing shell exposes permission-aware navigation and global Create
commands. Booking creation is being simplified to a four-to-six-field first
step with optional operational setup. Music has real catalog list/create/detail
flows; additional metadata/distribution/pitching screens remain explicitly
backend-contract work rather than fake UI. No production schema migration is
required for the web UX changes in this phase.
