# Storage Providers

Storage configuration supports private S3-compatible providers, including AWS S3-compatible APIs.
Only endpoint, region, bucket, prefix, status, and `EVOLVE_...` credential references are stored.
Actual access keys remain in server-managed environment secrets and never reach Django serializers,
audit events, logs, or the browser.

Tests resolve the HTTPS endpoint to public network addresses, then write, read, and delete a small
random object below `evolve-connectivity-tests/`. Cleanup is attempted on every failure. Absolute paths,
traversal segments, embedded URL credentials, localhost, private, link-local, and metadata-address
targets are rejected. Buckets remain private by default.

This milestone configures and tests providers only. Existing Documents are not migrated and general
uploads remain disabled. Authorized downloads, signed URLs, MIME and size validation, malware scanning,
retention, and deletion policy require a dedicated future milestone.
