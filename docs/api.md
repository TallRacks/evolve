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
