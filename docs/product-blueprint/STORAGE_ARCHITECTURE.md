# Evolve Storage Architecture

PostgreSQL stores application records through Django only. Production uses an internal Docker database network and an external persistent volume; port 5432 is not published.

Configured object storage is private by default. `StorageProvider` stores provider metadata and controlled environment-variable references, never secret values. Connection probes use server-generated objects and verify write/read/delete cleanup.

General binary uploads remain disabled until the selected private storage path and access controls are fully integrated. Documents currently represent metadata, links, generated text snapshots, and version lineage.

The service worker caches only the static offline route, Next.js static build assets encountered by the client, and the generated app icon. It never handles `/api/*` or `/admin/*`, and it does not cache authenticated navigation responses or operational data.
