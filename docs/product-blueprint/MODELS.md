# Evolve Model Architecture

Django and PostgreSQL are the persistence authority. Schema changes require migrations. This experience refinement adds no models and no migrations.

## Ownership boundaries

`users.User` is the sole application identity. `organizations.Organization` and active `Membership` records define ordinary access boundaries. Organization-owned domains include artists, relationships, bookings, call sheets, music, campaigns, documents, notifications, finance, rights, travel, production, contracts, tasks, reporting views, branding, and API clients.

## Important separations

- User identity is not Artist or Contact.
- Credit is not ownership.
- Ownership is not earnings.
- Earnings are not payment.
- Booking commercial terms are not Finance ledger entries.
- AuditEvent, Notification, and SecurityEvent are distinct.
- Production Advance is mutable preparation; Call Sheet versions are historical snapshots.
- Contract terms do not mutate Finance or Rights.

Historical and finalized records use explicit lifecycle services and immutable snapshots where implemented. Refer to domain documentation and migrations for field-level definitions.
