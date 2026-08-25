# Permissions

Django owns authorization. Organization access is centralized in
`organizations.permissions`; selectors scope reads in `organizations.selectors`. Frontend
navigation and portal routes are user experience only and never security boundaries.

```text
platform superuser -> active organization -> allowed
normal user        -> active user + active organization + active membership
permission         -> access above + permission granted by membership role
staff only         -> no implicit organization access
anonymous          -> denied
```

The initial permission vocabulary is intentionally small: organization view/manage and
membership view/manage. Owner has all organization permissions; administrator manages the
organization and memberships; manager can view the organization and memberships; member and
artist can view the organization. Application code asks for permission identifiers rather
than comparing role names. Future organization-owned querysets must start from an authorized
organization selector, never an organization ID supplied by a client alone.

Reusable DRF permission classes live in `organizations.api.permissions` for authenticated
users, active organization access, platform superusers, and artist access. Artist portal
access is represented by the backend-derived `portal.artist` permission. Platform access
requires an active Django superuser; `is_staff` alone never qualifies.

Frontend guards provide loading, redirect, and 403 user experience only. They consume
backend-derived bootstrap data but do not protect backend resources. Every future
organization-owned endpoint must independently resolve an authorized organization and apply
the relevant backend permission.

Organization owners and administrators may manage organization settings, memberships, and
invitations. Managers may view team and invitation information but cannot mutate access.
Members and artists may view their organization; artist memberships additionally receive
portal.artist. The final active owner cannot be demoted or deactivated.

Platform endpoints use the reusable PlatformSuperuser DRF permission. They expose no
staff-only shortcut: is_staff without is_superuser remains insufficient.

## White-label and developer permissions

The explicit organization permissions `branding.manage`, `domain.manage`, and `api.manage`
are granted to owners and administrators by the current role templates. Reading effective
branding still requires authorized organization access. Branding mutation, domain submission,
and API-client/key management require their matching permission. Platform branding and domain
operations require `is_superuser`; `is_staff` alone remains insufficient.

API scopes (`profile.read`, `organization.read`, and `team.read`) constrain integration keys.
They are not organization-role permissions and cannot expand the organization attached to the
API client. Hostname selection and frontend navigation never confer authorization.

## Artist permissions

`artist.view` allows organization directory/detail reads. `artist.manage` allows profile and
lifecycle changes. `artist.team.manage` controls assignments and portal links. Owners and
administrators receive all three; managers receive view/manage; members receive view; the artist
role receives only `portal.artist` and can see linked portal-safe data rather than the internal
artist directory. Platform superusers can manage artists across organizations. Staff status alone
never grants Artist access.

## Relationship management

`promoter.view/manage`, `venue.view/manage`, and `contact.view/manage` use the centralized organization permission map. Owners and administrators receive full permissions, managers receive view/manage, and members receive view only. Artist-role memberships receive none. Platform superusers have explicit cross-organization access; `is_staff` alone never bypasses organization scoping.

## Booking management

`booking.view`, `booking.manage`, `booking.status.manage`, and `booking.team.manage` separate reading, operational editing, controlled transitions, and team assignments. Owners and administrators receive full booking and commercial access. Managers receive operational booking permissions but not `booking.commercial.view/manage`; members receive read-only booking access with commercial fields omitted. Artist memberships receive none until an explicit artist-booking policy is approved. Platform superusers retain cross-organization access; staff status alone grants nothing.

## Call Sheet operations

`callsheet.view`, `callsheet.manage`, and `callsheet.publish` separate authenticated reads, draft/structured editing, and official publication. Owners, administrators, and managers receive all three. Members receive read-only access. Artist memberships receive no Call Sheet access until a dedicated published-view policy is approved. Platform superusers cross organizations; `is_staff` alone grants nothing. Booking assignment responsibility never creates Call Sheet authorization.

## Music permissions

The centralized permissions are `music.view`, `music.manage`, `music.release.manage`, `music.track.manage`, and `music.credits.manage`. Owners, admins, and managers receive Music management permissions; members receive read access. Artist-linked portal reads are separately scoped to authorized Artists. Platform-wide Music access requires an active Django superuser; `is_staff` is insufficient. Frontend route guards are UX only.

## Campaign and Rollout permissions

`campaign.view/manage/status.manage` and `rollout.view/manage/task.manage` use centralized Membership permissions. Owners, administrators, and managers manage plans; members receive read access; artist portal reads are separately limited to linked Artists. Platform access requires an active superuser, never `is_staff` alone.

## Calendar and documents

Milestone 12 adds a non-persisted, bounded calendar projection and standalone `CalendarEvent`, plus external-reference `Document` metadata with explicit version lineage and constrained same-organization typed links. Binary upload, external calendar sync, and notification delivery remain deferred. See `docs/calendar.md` and `docs/documents.md`.

## Notifications

Milestone 13 adds immutable shared Notification content, unique per-user recipient state, category preferences, and synchronous domain-service integration. Personal inbox data is not exposed to API keys. External and scheduled delivery remain deferred.

## Finance permissions

`finance.view/manage`, `finance.invoice.issue`, `finance.payment.record`, and
`finance.payment.allocate` belong to owners and administrators. Managers, members, artists, and
staff-only users receive none. Platform Finance requires superuser; API keys require the separate,
deliberately granted `finance.read` scope.
