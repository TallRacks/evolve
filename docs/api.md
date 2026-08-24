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
