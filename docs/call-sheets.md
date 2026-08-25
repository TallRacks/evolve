# Call Sheets

## Architecture

A Booking owns at most one CallSheet identity. A CallSheet owns sequential CallSheetVersion revisions. Version creation locks only the Call Sheet row before allocating `1, 2, 3...`; `(call_sheet, version_number)` is unique. Booking and nullable master relationships are then read without locks inside the same transaction. Under PostgreSQL's default read-committed isolation, each snapshot query sees committed source data while the Call Sheet lock serializes version allocation; master records are not locked because snapshotting does not mutate them. Copying a version deep-copies structured operational children so the new draft can change independently.

## Lifecycle and publication

- `draft`: editable working version; Booking snapshots may be explicitly refreshed.
- `ready`: reviewed working version eligible for publication.
- `published`: current official authenticated version and operationally immutable.
- `superseded`: previously published immutable history.
- `cancelled`: abandoned immutable working version.

Publishing is a transaction that locks the Call Sheet and versions, validates `callsheet.publish`, supersedes the previous published version, and publishes the ready version with actor/time metadata. A conditional database constraint permits one published version. Generic PATCH cannot change lifecycle state.

## Snapshots and sections

Event, artist, date/timezone, promoter, venue/address, and venue phone values are explicit snapshots. Draft-only Refresh from Booking updates only those Booking-derived fields; it does not overwrite schedule, access, production, hospitality, travel, accommodation, or notes. Master edits never rewrite published versions.

Ordered child records provide run-of-show, team call-time snapshots, operational contact snapshots, travel summaries, and accommodation summaries. Version fields provide compact venue/access, production, hospitality, and operational-note sections. Child source references are optional; snapshots remain authoritative.

Travel and accommodation are Call Sheet summaries only. There are no integrations or standalone domains, and passport, payment-card, finance, fee, deposit, and balance data are prohibited. Dietary notes should avoid unnecessary health data.

## Authorization and privacy

Django independently scopes every operation to the authorized organization. Owners, administrators, and managers can edit and publish; members have authenticated read access. Artist access remains deferred. Platform superusers have cross-organization administration; staff status alone grants nothing. Frontend routes are UX only.

Published and superseded versions and all children reject edits through API, services, models, and admin. The developer `callsheet.read` endpoint returns current published summaries only, without internal notes or personal team/contact details.

## Portals and export

The Booking Call Sheet landing route is `/workspace/bookings/{id}/call-sheet`; editors use `/workspace/call-sheets/{versionId}` and authenticated read/print views use `/workspace/call-sheets/{versionId}/view`. Platform inventory uses `/platform/call-sheets`. The HTML view includes print CSS suitable for browser A4/Letter output. Server PDF rendering is deferred to avoid adding browser infrastructure.

Anonymous sharing, expiring links, revocation, password protection, email/SMS distribution, notifications, and public field-level privacy policies are deferred.

## Calendar and documents

Milestone 12 adds a non-persisted, bounded calendar projection and standalone `CalendarEvent`, plus external-reference `Document` metadata with explicit version lineage and constrained same-organization typed links. Binary upload, external calendar sync, and notification delivery remain deferred. See `docs/calendar.md` and `docs/documents.md`.

## Travel integration

See `docs/travel.md` for the implemented Travel integration and its authorization, privacy, and snapshot rules.

## Production import

A draft Call Sheet version can explicitly import the linked Booking's Production Advance. The service copies schedule, operational contacts, access/parking context, and selected safe requirement titles into the draft. Existing corresponding draft rows are replaced. Published, superseded, and cancelled versions reject import and never update dynamically.
