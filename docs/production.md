# Production Advancing

## Boundary

The `production` Django app owns the editable show-preparation layer. A
`ProductionAdvance` belongs to one organization and one Booking, and the Booking
determines its Artist. A Booking has at most one canonical advance. Venue and
Promoter references are copied from the Booking when the advance is created and
do not silently follow later Booking changes.

Production does not own Artists, Bookings, Venues, Promoters, Contacts, Travel,
Call Sheets, Documents, users, or organizations. It references those domains.

## Lifecycle

The lifecycle is `draft`, `in_progress`, `ready`, `confirmed`, `completed`,
`cancelled`, and `archived`. Explicit service actions validate transitions and
lock the direct advance row. Generic updates cannot change status. Django admin
exposes status as read-only so it cannot bypass the service.

## Operational records

An `AdvanceRequirement` describes what must be agreed or provided. It carries a
structured category, source, priority, status, optional assignee, response, due
time, and sequence. Confirmed and not-applicable requirements count as complete.

An `AdvanceChecklistItem` describes an action the internal team must perform.
Completion and reopening are explicit, attributed operations. The checklist is
limited to one Production Advance and does not replace Rollout Tasks.

`ProductionContactAssignment` links an existing organization Contact to an
operational role. It does not create a second contact database. The database
allows multiple contacts per role but only one active primary assignment for a
role and advance.

`ProductionScheduleItem` records venue/show operations with timezone-aware
timestamps and an explicit IANA timezone. Travel transport remains in the Travel
domain. Schedule end time, when supplied, must be later than start time.

## Authorization and privacy

All workspace selectors are organization scoped. Owners and administrators have
full access; managers receive operational management; members receive the
configured read access. Django superusers may cross organizations. `is_staff`
alone never grants platform or cross-organization access.

Artist portal responses are read-only and curated. They include safe show
timing, primary contact identity/role, and Artist-sourced requirements. They omit
management, security, checklist, personal contact-detail, audit, and internal
note fields. The developer `production.read` scope exposes only a conservative
organization-scoped summary.

## Integrations

- Booking detail creates or opens its canonical Production Advance.
- Venue and Promoter details project related organization-scoped advances.
- Production links to the Booking Travel itinerary without copying it.
- Documents use an explicit typed `production_advance` link; binary upload
  remains disabled.
- Calendar projects advance due dates and active schedule items. Booking remains
  the source for the show event, so a Production `show` item is not duplicated.
- Notifications are synchronous, sparse, and contain no notes, security detail,
  contact data, or other sensitive content.
- Search uses title, Artist, Booking reference, Venue, and Promoter only.

## Call Sheet snapshot

Production Advance is mutable preparation. Call Sheet versions are historical
snapshots. A user must explicitly import Production into a draft Call Sheet
version. The import replaces the corresponding draft schedule and contact rows
and copies selected safe operational fields. It never imports checklist or
security detail. Published, superseded, and cancelled versions are rejected and
future Production changes never update a Call Sheet automatically.

## Audit and deferred depth

Creation, updates, transitions, child mutations, completion/reopening, removal,
reordering, and Call Sheet imports emit audit events containing identifiers and
state rather than note contents. Detailed riders, patch sheets, stage plots,
equipment/inventory, external advancing integrations, uploads, and PDF
generation remain deferred.
