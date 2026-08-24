# Music catalog

Milestone 10 establishes the organization-owned Music catalog. Django remains the authorization and business-rule authority.

## Model

- `Release` is a commercial release container owned by an Organization and primarily associated with one Artist.
- `Track` is a reusable recording. `version_title` distinguishes genuine variants; adding a Track to another Release does not duplicate it.
- `ReleaseTrack` holds deterministic disc, track, and sequence ordering plus focus-track designation. Removing a placement does not delete the Track.
- `MusicCredit` describes release or track contributors. Contributors may be name-only or link to a same-organization Artist or Contact. Credits do not represent royalty ownership.
- `ReleaseLink` stores constrained DSP/public URLs. No DSP API integration exists.

## Identifiers

ISRC values are normalized to uppercase without spaces or hyphens and validated as 12 characters. Non-empty ISRC values are globally unique. UPC/EAN values are numeric, 8-14 digits, and globally unique when non-empty. Evolve does not issue either identifier.

## Lifecycle

Release transitions are centralized and row locked: draft to scheduled or cancelled; scheduled to draft, released, or cancelled; released to archived. Scheduling requires a planned date. Cancelled and archived are terminal. Generic release updates cannot change status.

Released tracklists remain correctable by authorized operators. Corrections are audited rather than making released catalog data immutable.

## Access

Workspace access uses `music.view`, `music.manage`, `music.release.manage`, `music.track.manage`, and `music.credits.manage`. Organization scope is enforced by Django. Platform superusers have explicit cross-organization views; `is_staff` alone has no bypass. Linked artist-portal users receive read-only scheduled/released releases and active tracks for authorized linked Artists only; internal notes are excluded.

## APIs and UI

Workspace APIs are under `/api/music/`; artist catalog bootstrap is `/api/artist-portal/music/`; platform-superuser views are under `/api/platform/music/`. Integration clients with `music.read` may use `/api/developer/releases/` and `/api/developer/tracks/`; responses are curated and omit internal notes, audit data, and private business metadata.

Workspace routes live under `/workspace/music`; platform routes live under `/platform/music`. Django Unfold provides protected Music administration and uses the lifecycle service for release status changes.

## Campaign relationships

Campaign now references `Campaign -> Release -> Artist` where a Release is applicable. Operational execution uses `Campaign -> Rollout -> milestones/tasks`; Music data is referenced rather than duplicated. See [`campaigns.md`](campaigns.md) and [`rollouts.md`](rollouts.md).

Territory-specific schedules, DSP integrations, audio/object storage, distribution feeds, rights, royalties, publishing ownership, accounting, invoices, and payments are deferred.

## Calendar and documents

Milestone 12 adds a non-persisted, bounded calendar projection and standalone `CalendarEvent`, plus external-reference `Document` metadata with explicit version lineage and constrained same-organization typed links. Binary upload, external calendar sync, and notification delivery remain deferred. See `docs/calendar.md` and `docs/documents.md`.
