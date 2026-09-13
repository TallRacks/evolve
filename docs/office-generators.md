# Office generators

Booking and Release Office generators are deterministic server-side services. They read authoritative domain records and write validated native Office JSON; they never use AI or copy mutable business logic into templates.

## Reuse policy

Booking Brief, Show-Day Brief, Production Notes, and the Release One-Sheet, Metadata Sheet, Credits Sheet, Campaign Brief, and Release Checklist each reuse the active generated Office item for the linked source record. A rerun returns that item and preserves manual edits. Meeting Notes are intentionally non-idempotent because multiple meetings are valid.

Refresh is explicit: a future refresh operation must preview or create a new revision, and must never silently replace user-edited content. Generated items are organization-visible, linked to their source and Artist where supported, and are never public.

Booking generation requires `booking.view` and `document.manage`; Release generation requires `music.view` and `document.manage`. Commercial booking values, private contact details, rights ownership, and royalty data are excluded from generated content unless a separately authorized field is explicitly added.
