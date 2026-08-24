# Database

PostgreSQL is Evolve's system of record and Django is its only access layer. The project user
model is permanently `users.User`; changing `AUTH_USER_MODEL` after this milestone is not a
supported migration path.

Identity data uses UUID primary keys. `Membership` has a database uniqueness constraint on
user and organization. Invitation token digests are unique and raw invitation tokens are not
stored. Schema changes use reviewed Django migrations only.

Production uses the external `evolve_postgres_data` volume without a published host port.
Credentials remain in `/opt/evolve/secrets/evolve.env`. Backup, restore, retention, and
production connection-pool policies remain operational decisions to finalize before broader
product data is introduced.
