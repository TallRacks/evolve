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
