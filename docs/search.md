# Global Search

`GET /api/search/?q=<query>&organization_id=<uuid>` is authenticated, read-only, and implemented with bounded Django/PostgreSQL queries. Queries require 2-100 characters and return at most six curated results per group.

Search can return Artists, Bookings, Promoters, Venues, Contacts, Releases, Tracks, Campaigns, Works, Documents, and permission-gated Invoice references. It never returns full serializers, notes, payment data, royalty earnings, audit descriptions, credentials, invitation tokens, or restricted Documents.

Each domain group is enabled only when Django confirms the corresponding permission for an active membership. Document results additionally reuse Document visibility selectors. Artist-role and staff-only accounts receive no workspace-wide results. Platform superusers may intentionally search across active organizations when no organization filter is supplied.

Results contain only an ID, type, title, subtitle, internal destination, and optional status. Search reads are not audited.
