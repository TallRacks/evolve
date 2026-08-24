# Artists

## Domain boundary

Artist is an organization-owned managed business entity, not a `users.User`. An artist can exist
without a login. UUIDs are internal/public identifiers and slugs are stable and unique within the
owning organization. Profile assets use URL references; richer artist branding, uploads, and
arbitrary CSS are deferred.

Lifecycle is explicit: `active`, `inactive`, or `archived`. Deactivation and archive transitions
preserve history. Application and Django-admin deletion are disabled.

## Teams and portal links

`ArtistTeamAssignment` links an artist to an effective active organization membership. Its
responsibility (`manager`, `booking`, `marketing`, `finance`, or `general`) describes operational
responsibility and does not confer permissions. Cross-organization, duplicate, inactive-member,
and multiple-primary relationships are rejected.

`ArtistPortalLink` is a scalable association between Artist and User. A link never authenticates or
authorizes a user. Artist portal reads require an active link, active user/organization/membership,
and the backend `portal.artist` permission. Multiple linked artists are supported; platform
superusers do not impersonate artist portal users.

## Authorization and APIs

Django centrally enforces `artist.view`, `artist.manage`, and `artist.team.manage`. Client-supplied
organization IDs, artist UUIDs, slugs, membership IDs, and user IDs are always resolved through
scoped querysets and relationship validation. Owners/admins fully manage artists; managers edit
profiles; members can read the internal directory; artist-role members see only authorized linked
portal data. `is_staff` has no bypass; superusers have explicit platform access.

Workspace APIs live under `/api/artists/`; portal bootstrap is `/api/artist-portal/`; platform APIs
are `/api/platform/artists/`. Integration keys with `artist.read` may call the curated read-only
`/api/developer/artists/` endpoint and remain bound to their API client's organization.

## Audit and future domains

Creation, update, lifecycle changes, team assignment/update/removal, and portal link/unlink actions
produce `artist.*` audit events without secrets. Bookings, Music, Campaigns, Documents, detailed
artist branding, and integration writes remain future domains.
