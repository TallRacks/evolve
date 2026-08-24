# Database

PostgreSQL is Evolve's system of record. Django is the sole database access layer; browser
and frontend code must use the Django API.

Schema changes are represented by committed Django migrations. Generate and review each
migration alongside its model change, and validate that no uncommitted migrations remain.
Avoid manual production schema changes.

Compose stores local data in the named `postgres_data` volume and does not publish port
5432 to the host. Credentials and connection URLs come from environment variables. Backup,
restore, retention, and production connection-pool policy will be defined before launch.
