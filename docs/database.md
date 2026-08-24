# Database

PostgreSQL is Evolve's system of record and Django is its only access layer. The project user
model is permanently `users.User`; changing `AUTH_USER_MODEL` after this milestone is not a
supported migration path.

Identity data uses UUID primary keys. `Membership` has a database uniqueness constraint on
user and organization. Invitation token digests are unique and raw invitation tokens are not
stored. Schema changes use reviewed Django migrations only.

AuditEvent stores immutable mutation history with UUID identity, actor, optional organization,
action, resource reference, description, request IP, and timestamp. Audit records never
contain credentials, invitation tokens, or token digests.

Production uses the external `evolve_postgres_data` volume without a published host port.
Credentials remain in `/opt/evolve/secrets/evolve.env`. Backup, restore, retention, and
production connection-pool policies remain operational decisions to finalize before broader
product data is introduced.

## White-label records

`OrganizationBranding` is a one-to-one organization configuration with validated color tokens,
URL references, and support metadata. Defaults are computed when no row exists. `OrganizationDomain`
normalizes and globally uniquifies hostnames, records a DNS challenge and verification state,
and constrains each organization to one active primary domain.

`APIClient` belongs to one organization. `APIKey` stores a display prefix, SHA-256 secret digest,
allowlisted scopes, timestamps, expiry, and revocation state. Raw API secrets are never persisted.
The `white_label.0001_initial` migration creates these four tables and their constraints.

## Artist records

`Artist` uses a UUID primary key, organization ownership, an organization-scoped unique slug, and
the lifecycle values active, inactive, and archived. `ArtistTeamAssignment` uniquely pairs an
artist and membership and constrains each artist to one effective primary assignment.
`ArtistPortalLink` uniquely pairs an artist and user. Domain validation rejects cross-organization
or ineffective membership relationships. Operational workflows deactivate/archive records rather
than deleting them. These tables are introduced by `artists.0001_initial`.

## Relationship records

`contacts_contact`, `promoters_promoter`, and `venues_venue` hold organization-owned UUID master records. Relationship tables connect promoter/contact and venue/contact records with same-organization validation, constrained responsibility, active state, and conditional primary-per-role uniqueness. Promoter and venue slugs are unique per organization. Schema creation uses the three normal `0001_initial` migrations.

## Booking records

`bookings_booking` stores organization-owned events with UUID identity, a globally unique public reference, artist and optional promoter/venue references, schedule, lifecycle, priority, operational notes, and permission-gated commercial terms. Selected promoter, venue, city, and country values are frozen snapshots. Status history is append-only. Team and contact assignments enforce same-organization relationships and conditional primary uniqueness; assigned contact identity fields are snapshotted. `bookings.0001_initial` creates the domain after its master-record dependencies.

## Call Sheet records

`callsheets_callsheet` is a one-to-one operational document identity for Booking. `CallSheetVersion` has a unique sequential number per Call Sheet and a conditional database constraint permitting one published version. Explicit snapshot columns preserve event, venue, access, production, hospitality, and note data. Ordered child tables store schedule, team, contact, travel, and accommodation snapshots. Foreign keys protect historical rows from source deletion. `callsheets.0001_initial` creates the domain after Booking, Membership, Contact, and User dependencies.

## Music catalog

`music.Release` and `music.Track` use UUID primary keys and organization-scoped slugs. `music.ReleaseTrack` provides ordered many-to-many placement. `music.MusicCredit` targets at least one Release or Track. `music.ReleaseLink` stores constrained public URLs. Database constraints enforce non-empty global ISRC/UPC uniqueness, placement uniqueness, disc/track uniqueness, one primary release link, and the credit target requirement. Schema is introduced by `music.0001_initial`.
