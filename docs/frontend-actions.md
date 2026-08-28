# Frontend actions and forms

## Page classification

Every frontend route is treated as one of three types:

- **Full action page**: a mutable domain surface. Applicable create, edit, relationship, lifecycle, and semantic removal actions must complete through the Django API and domain service layer.
- **Read-only by design**: a curated portal, platform inspection, projection, history, print, search, dashboard, or overview surface. Its appropriate actions are navigation, selection, preview, or print; it does not acquire mutation rights for symmetry.
- **System page**: authentication, invitation acceptance, application bootstrap, or developer documentation.

The source inventory is the Next.js App Router tree under `frontend/app`. Shared implementations live in `frontend/components`; route files do not confer authorization.
At the Milestone 20 checkpoint the source inventory contains 137 page routes: 70 full-action pages, 61 read-only-by-design pages, and 6 system pages. Workspace domain lists, create forms, mutable details, settings, notifications, and legitimate platform administration are full-action. Artist portal, platform domain inspection, dashboards/overviews, history, and print views are read-only by design. Root, login, invitation acceptance, and developer reference surfaces are system pages.

## Action standard

List pages expose a visible Create action when standalone creation is valid, plus search/filtering appropriate to current API scale, loading, error, empty, and open-row states. Context-owned records remain contextual: Call Sheets and Production Advances originate from Bookings.

Mutable detail pages expose Edit directly. Lifecycle and consequential relationship actions use explicit labels such as Archive, Deactivate, Cancel, Void, Remove, Revoke, or Terminate. Buttons are permission-aware UX only; Django reauthorizes every request and organization relationship.

Rendered actions must call a real route. Placeholder buttons, `href="#"`, browser `confirm()`/`prompt()`, and fake submit handlers are prohibited.

## Forms

Forms load current values for editing, retain decimal strings for money and percentages, use local date/time controls with explicit timezone context, prevent accidental duplicate submission where consequential, and display safe server validation. Organization-owned selectors are populated only from scoped APIs. Cancel navigation must not mutate data.

The shared API client distinguishes validation, authentication, authorization, not-found, conflict, processing, and server failures without exposing traceback or server internals. Django serializer and domain-service validation remains authoritative.

## Confirmations

Consequential actions use the shared accessible action dialog. A confirmation states the action and consequence, identifies the record where useful, supports a required reason when policy needs one, retains keyboard cancellation, and prevents mutation until confirmed. Browser-native confirmation dialogs are not used.

## Semantic removal

Historical records are not generically deleted:

- users, memberships, organizations, artists, contacts, promoters, and venues are deactivated or archived;
- bookings, campaigns, rollouts, releases, travel, and production are cancelled or archived through lifecycle services;
- invoices, payments, and royalty statements are voided;
- contracts are terminated or archived;
- invitations and API credentials are revoked;
- published Call Sheet versions are immutable and never deleted;
- disposable draft child relationships may be removed only through scoped services.

## Immutable-state UX

Published, finalized, executed, voided, superseded, cancelled, and otherwise immutable states hide edit controls and remain viewable as history. The backend rejects direct lifecycle PATCH and historical child mutation even when a client submits one manually.

## Call Sheet generation

`/workspace/bookings/{bookingId}/call-sheet` is the canonical generation landing page. Generate Call Sheet idempotently locates or creates the Booking's single CallSheet and first draft. If a working draft exists, the primary action opens it. If only immutable history exists, Create New Version copies a selected prior snapshot while allocating the next version under PostgreSQL row locking.

A draft can explicitly refresh Booking snapshot fields and import current Production and Travel operational data. Imports replace only the documented draft sections. They never update published history. The editor supports overview, ordered schedule, team, contacts, venue/access, travel, accommodation, production, hospitality, notes, readiness, cancellation, and publication.

The read route is both draft preview and historical/published view. Draft, superseded, and cancelled states are visibly labelled. Empty sections are omitted. Published output includes organization, artist, event, date, venue, version, publication metadata, and populated operational sections.

Print / Save PDF invokes the browser print dialog. Print CSS removes application navigation and controls, uses print-safe contrast and margins, and avoids splitting operational sections where practical. There is no server-side PDF renderer.
