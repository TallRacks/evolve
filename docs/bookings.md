# Bookings

Bookings are organization-owned operational event records. Each booking requires an Artist and may reference current Promoter, Venue, Contact, and Membership records from the same organization.

Finance remains separate. Authorized users explicitly create a draft Invoice snapshot from current
commercial terms. Booking changes never synchronize into that invoice, and Finance-derived totals
are not duplicated onto Booking.

## Identity and lifecycle

Bookings use UUID primary keys and globally unique server-generated `EV-` references. The supported workflow is:

```text
enquiry -> hold | pending | declined
hold -> pending | confirmed | cancelled
pending -> confirmed | declined | cancelled
confirmed -> completed | cancelled
completed | cancelled | declined -> terminal
```

Only the status transition service may change status. Every successful transition creates append-only status history and an audit event. Generic updates reject status changes.

## Historical snapshots

Artist remains a live required reference. Promoter and Venue remain optional live references, while their selected name and location values are copied into the booking. Assigned contacts copy name, email, and phone. Later edits to master records do not silently rewrite these snapshots. Explicitly selecting a different Promoter or Venue refreshes the corresponding booking snapshot.

## Authorization

All reads and mutations are authorized and organization scoped by Django. Owners and administrators have full operational and commercial access. Managers can manage operational fields, transitions, contacts, and team assignments without seeing or changing commercial terms. Members have safe read-only access. Artist memberships do not receive internal booking access in this milestone. Platform superusers can work across organizations; `is_staff` alone grants no access.

Commercial values are conditionally included only for `booking.commercial.view` and may be changed only with `booking.commercial.manage`. List and developer serializers exclude them.

## API and portals

Workspace routes are `/workspace/bookings`, `/workspace/bookings/new`, and `/workspace/bookings/{id}`. Platform routes are `/platform/bookings` and `/platform/bookings/{id}`. These frontend routes are user experience only.

Session APIs are rooted at `/api/bookings/`, with explicit nested status, status-history, team, and contact routes. Platform list/detail routes are rooted at `/api/platform/bookings/`. `GET /api/developer/bookings/` requires `booking.read` and returns a curated organization-scoped directory without commercial terms, notes, contacts, team, or audit data. Booking write integrations are not implemented.

Each Booking may now own one versioned Call Sheet operational document. Booking remains the commercial and event source of truth; Call Sheet versions preserve execution snapshots and never include commercial terms. See [`call-sheets.md`](call-sheets.md). Settlement and artist-portal Booking visibility remain deferred.

## Calendar and documents

Milestone 12 adds a non-persisted, bounded calendar projection and standalone `CalendarEvent`, plus external-reference `Document` metadata with explicit version lineage and constrained same-organization typed links. Binary upload, external calendar sync, and notification delivery remain deferred. See `docs/calendar.md` and `docs/documents.md`.

## Travel integration

See `docs/travel.md` for the implemented Travel integration and its authorization, privacy, and snapshot rules.

## Production Advance

Booking detail can explicitly create or open its one canonical Production Advance. Production derives organization and Artist from Booking and reports progress, blocked requirements, checklist progress, and the next operational schedule item without duplicating those records on Booking.
