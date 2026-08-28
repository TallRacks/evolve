# Integration API

The canonical base URL is `https://evolve.nastycsa.com/api/`, including for organizations using
a white-label web hostname. The authenticated developer portal is available at `/developer`,
`/developer/api`, `/developer/keys`, and `/developer/docs`.

The currently implemented integration endpoint is:

- `GET /api/developer/whoami/` with scope `organization.read`; returns only API client identity,
  organization identity, and granted scopes.

Initial allowlisted scopes are `profile.read`, `organization.read`, and `team.read`. No business
product scopes exist. Browser session endpoints continue to use Django sessions and CSRF and are
separate from integration authentication. Curated documentation was chosen for this milestone;
OpenAPI generation is deferred until the public integration surface is large enough to justify it.
Production API rate limiting is not implemented and is explicitly deferred without introducing
Redis.

Artist integrations add the allowlisted `artist.read` scope and the read-only endpoint
`GET /api/developer/artists/`. It returns a curated organization-scoped directory containing
identity, lifecycle, location, website, image reference, and update time. It excludes legal names,
private contact fields, team data, portal links, and audit data. Artist write scopes and integration
write endpoints are deferred.

## Relationship APIs

Session APIs provide explicit organization-scoped list/create/detail/update routes for `/api/promoters/`, `/api/venues/`, and `/api/contacts/`. Promoter and venue contact relationships use nested `/contacts/` routes and deactivate links instead of deleting them. `search` and lifecycle filters support future selectors without a separate search service.

Read-only integration endpoints `/api/developer/promoters/` and `/api/developer/venues/` require `promoter.read` and `venue.read` respectively. Responses are organization scoped and curated. Contact notes and relationship contact details are not exposed through developer endpoints.

## Booking APIs

Session endpoints provide organization-scoped booking list, create, detail, and update operations. Status transitions, status history, team assignments, and contact assignments use explicit nested endpoints. Generic booking updates cannot change status. Platform routes provide superuser cross-organization administration.

`GET /api/developer/bookings/` requires `booking.read`. Its organization-scoped response is read-only and intentionally excludes commercial terms, internal notes, contact details, and audit data. No booking write scope exists.

## Call Sheet APIs

Session endpoints create or retrieve a Booking's single Call Sheet, create sequential versions, edit draft/ready snapshots, manage structured schedule/team/contact/travel/accommodation children, and invoke explicit ready, publish, cancel, and refresh operations. Publication cannot occur through generic PATCH. Platform endpoints provide superuser inventory/detail access.

`GET /api/developer/call-sheets/` requires `callsheet.read` and returns only current published summaries for the API client's organization. It excludes schedule details, personal contact information, internal notes, commercial terms, and historical superseded versions. No Call Sheet write scope exists.

## Music integration API

API credentials may receive `music.read`. `GET /api/developer/releases/` and `GET /api/developer/tracks/` are read-only and organization scoped. Responses contain curated public catalog fields and exclude internal notes, audit history, and private business metadata.

## Campaign APIs

`campaign.read` enables organization-scoped `GET /api/developer/campaigns/` and `GET /api/developer/rollouts/`. Responses contain curated identity, lifecycle, dates, relationships, and computed progress. Internal descriptions, task details, assignee contact data, and audit history are excluded.

## Calendar and documents

Milestone 12 adds a non-persisted, bounded calendar projection and standalone `CalendarEvent`, plus external-reference `Document` metadata with explicit version lineage and constrained same-organization typed links. Binary upload, external calendar sync, and notification delivery remain deferred. See `docs/calendar.md` and `docs/documents.md`.

## Finance API

The deliberately granted `finance.read` scope enables organization-scoped read-only
`GET /api/developer/finance/invoices/` and `GET /api/developer/finance/payments/`. Representations
contain financial identity, lifecycle, currency, totals/balance, and dates. They exclude billing
addresses/emails, payer identity, internal notes, audit data, and allocation actors.

## Rights API

rights.read enables organization-scoped GET /api/developer/rights/works/ and
GET /api/developer/rights/tracks/. Private contacts, notes, contracts, audit data, and royalty
earnings are excluded. royalties.read is deliberately not implemented.

## Consolidation APIs

- `GET /api/search/?q=&organization_id=` returns capped, grouped, permission-filtered search results.
- `GET /api/dashboard/?organization_id=` returns a curated role-aware operational summary.
- `GET /api/artists/{id}/overview/` returns the workspace-authorized Artist 360 summary without finance or royalty earnings.

## Travel API

Workspace endpoints under `/api/travel/` provide scoped itinerary, traveller, segment, assignment, accommodation, room, reorder, and explicit lifecycle operations. `/api/artist/travel/` is a curated attributed read. `/api/platform/travel/` requires superuser. `GET /api/developer/travel/itineraries/` requires `travel.read` and excludes private contacts, references, notes, and private URLs.

## Production

Workspace APIs are rooted at `/api/production/advances/` with explicit status and requirement, contact, schedule, and checklist actions. `/api/artist/production/` is curated read-only data. `/api/platform/production/` requires platform superuser access. `/api/developer/production/advances/` requires the read-only `production.read` scope and excludes notes, Contact details, checklist, Documents, and audit data.

## Contracts API

Workspace endpoints under `/api/contracts/` provide scoped list, detail, child, approval, signing-state, lifecycle, Document-link, and Booking-create workflows. `/api/artist/contracts/` is curated executed-only data; `/api/platform/contracts/` requires superuser; `/api/developer/contracts/` requires `contract.read` and excludes legal text, values, parties, approvals, Documents, and internal notes.
