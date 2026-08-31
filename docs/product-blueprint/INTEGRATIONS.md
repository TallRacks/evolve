# Evolve Integrations

Implemented platform configuration covers SMTP email connectors and S3-compatible/AWS S3 storage providers. Records contain safe metadata plus controlled `EVOLVE_...` environment references. Secrets remain external to Git and the database.

Platform connector and storage mutation/testing requires an active superuser; `is_staff` is not a bypass. Automatic email delivery and general uploads remain disabled.

White-label domains and branding are organization-scoped routing/presentation metadata and never grant access. Developer API clients use explicit scopes and one-time raw keys stored as digests.

No Redis, Celery, scheduler, WebSocket, or microservice infrastructure is introduced by the experience refinement. Browser push is not claimed as implemented until a server-side subscription and delivery design exists.
