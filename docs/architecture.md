# Architecture

Evolve uses a same-origin, layered web architecture:

```text
Internet
   |
   v
Caddy
   |
   v
Next.js frontend
   |
   v
Django API
   |
   v
PostgreSQL
```

Caddy is the only public entry point and terminates TLS. Requests are routed as follows:

| Path | Destination |
| --- | --- |
| `/` | Next.js frontend |
| `/api/*` | Django API |
| `/admin/*` | Django admin |
| `/static/*` | Django static files |

The diagram expresses ownership and request flow: browser code calls the Django API
through the same public origin and never connects to PostgreSQL. Django owns data access,
authentication, authorization, validation, and business logic. Next.js owns presentation
and browser interaction.

The initial Compose stack contains PostgreSQL, Django, and Next.js. Caddy is deliberately
excluded because the VPS already runs it independently. In production, all application
services join private Docker networking and only Caddy publishes host ports 80 and 443.

No asynchronous worker, cache, message broker, or microservice is part of this foundation.
Those components require a demonstrated need and an explicit architecture decision.

## Production topology

The canonical origin is `https://evolve.nastycsa.com`. Caddy is independently managed and
joins `evolve_proxy` with the frontend and backend. Django and PostgreSQL additionally share
the internal `evolve_database` network; Caddy and the frontend cannot reach PostgreSQL.
Application containers expose ports only to Docker networks, while Caddy alone publishes
host ports 80 and 443.

## Portal and authorization boundaries

Next.js presents `/login`, `/dashboard`, `/platform`, `/workspace`, and `/artist`. These routes
separate future user experiences but confer no authority. Django sessions identify users, and
Django organization permission helpers enforce all data access. Django `/admin/` remains the
platform-superuser operations interface.

The App Router root installs a small client-side auth provider. It bootstraps from
`/api/auth/me/`, holds no credential or session token, and uses same-origin cookies for API
requests. Client route guards improve navigation but do not replace Django permissions.
Organization selection is tab-local presentation state; backend requests must reauthorize
any supplied organization identifier.
## Management portals

The authenticated Next.js shell has a persistent desktop sidebar and a mobile slide-over.
Workspace routes provide organization overview, team, invitations, and settings. Platform
routes provide superuser-only organization, user, and audit views. The profile route provides
safe self-service name editing. Django admin remains a separate Unfold operations console.

Explicit DRF API views serve only the data and mutations required by these routes. They
resolve organization identifiers through authorized querysets and record important mutations
in the read-only AuditEvent log.

## White-label and integration boundaries

Branding, domain mappings, API clients, and API keys live in the `white_label` Django app.
The authenticated shell requests effective branding for an organization that Django has
already authorized. A verified, active, primary hostname may select tenant presentation
context, but host resolution never creates membership or permission.

The canonical integration API remains `https://evolve.nastycsa.com/api/`. Integration keys
use an isolated Bearer-key path and do not replace Django session authentication. Caddy
configuration is not dynamically managed by the application.

## Artist domain

`artists.Artist` is the first business-domain entity and belongs to one organization. It is not an
authentication identity. `ArtistTeamAssignment` describes a membership's responsibility for one
artist without changing that membership's authorization role. `ArtistPortalLink` associates users
with artists, but portal reads additionally require an active artist-role membership in the same
organization. Workspace and platform routes call explicit Django APIs; organization branding
continues to theme the shared shell.

## Relationship domains

Promoters, Venues, and Contacts are separate organization-owned Django domains. PromoterContact and VenueContact provide reusable same-organization relationships. Django services and model validation remain authoritative for mutation, scoping, lifecycle, and audit behavior.

## Booking domain

Bookings are organization-owned operational records linked to an artist and optional promoter and venue masters. Selected partner, location, and contact values are frozen into booking snapshots for historical accuracy. Django services own transition validation, commercial-field authorization, assignment validation, and audit recording. Next.js workspace and platform booking routes remain presentation only.

## Call Sheet domain

Each Booking may own one CallSheet identity with sequential CallSheetVersion revisions. Versions contain explicit event and venue snapshots plus ordered schedule, team, contact, travel, and accommodation records. Django serializes version creation and publication, supersedes the previous published version atomically, and protects published operational history. Next.js provides authenticated editing and print views only; anonymous distribution and PDF rendering infrastructure are deferred.

## Music domain

The `music` Django app owns Release, Track, ReleaseTrack, MusicCredit, and ReleaseLink persistence and business rules. Next.js consumes same-origin Django APIs for workspace, artist, and platform Music views. Future Campaign and Rollout domains may reference Release but are not implemented. See [`music.md`](music.md).

## Marketing planning

The `campaigns` Django app separates organization-owned Campaign strategy from Rollout execution. Rollouts contain milestones, tasks, and validated dependencies. Future Calendar is a read projection and future Notifications consume audit/date state; neither is a standalone domain in Milestone 11.

## Calendar and documents

Milestone 12 adds a non-persisted, bounded calendar projection and standalone `CalendarEvent`, plus external-reference `Document` metadata with explicit version lineage and constrained same-organization typed links. Binary upload, external calendar sync, and notification delivery remain deferred. See `docs/calendar.md` and `docs/documents.md`.

## Notifications

Milestone 13 adds immutable shared Notification content, unique per-user recipient state, category preferences, and synchronous domain-service integration. Personal inbox data is not exposed to API keys. External and scheduled delivery remain deferred.

## Finance

The `finance` Django app owns Invoice, InvoiceLineItem, Payment, and PaymentAllocation. Booking
commercial terms are explicit creation inputs only; issued snapshots are independent. PostgreSQL
row locks serialize allocations. Next.js provides workspace, platform, and print presentation.

## Rights and royalties

The rights Django app owns Works, Track links, independent Rights Parties, Master/Publishing
ownership, Royalty Statements, lines, and earnings allocations. It references Music and Documents
without reinterpreting catalog credits or merging with Finance. PostgreSQL parent/line locks
protect split and allocation integrity.
