# Documents

Documents are organization-owned records with three explicit sources: `external` HTTPS references,
backend-generated text snapshots, and private `stored` binary files. PostgreSQL stores metadata and
lineage; the configured `integrations.StorageProvider` stores binary objects. The browser receives no
provider credential, internal object key, filesystem path, or permanent public object URL.

## Upload and validation

`POST /api/documents/upload/` accepts authenticated multipart uploads only for users with
`document.manage`. The default maximum is 25 MiB (`EVOLVE_MAX_UPLOAD_BYTES`). Accepted types are PDF,
DOCX, XLSX, PPTX, CSV, UTF-8 text, PNG, JPEG, and WebP. Evolve detects file signatures or validates
Office ZIP structure instead of trusting the browser MIME value. HTML, SVG, scripts, executables,
unknown binary data, malformed Office archives, and extension/content mismatches are rejected.

Original filenames are normalized, stripped of path/control characters, and retained only as display
metadata. Object keys are random, server-generated, organization/document/version scoped, and never
serialized. A SHA-256 checksum is recorded and only an abbreviated form is exposed in authenticated
Document detail metadata. Travel uploads with passport, identity-card, national-ID, or visa identity
filenames are explicitly rejected; those identity documents are outside Evolve's supported storage
policy.

File-type validation is not malware scanning. Upload access remains limited to trusted organization
operators. Broader untrusted upload use requires a deliberately integrated malware scanning/quarantine
policy before rollout.

## Versioning and retention

Each version is a new `Document` row in a root lineage. The root row is locked while allocating the next
version number, and the database unique constraint protects lineage numbering. Historical metadata and
objects are never overwritten. New versions inherit the selected Document's typed links.

Archive is non-destructive: metadata is marked archived and the provider object is retained. Generic
hard delete is disabled. Retention duration, legal holds, object purge, restore, bulk reconciliation,
and provider-to-provider migration remain deferred policy decisions.

## Authorization and downloads

Django authorizes every upload, metadata read, preview, download, link, version, and archive operation.
`document.view`, `document.manage`, `document.restricted.view`, organization isolation, Artist portal
scope, and explicit platform-superuser behavior remain authoritative; `is_staff` grants no bypass.
Documents used by Contracts, Rights Works, or Royalty Statements additionally require their respective
domain view permission. Artist portal access requires explicit `ARTIST` visibility and an allowed linked
Artist. The API-key developer endpoint remains metadata-only and exposes no binary download URL.

Stored content is streamed by Django from the provider. PDF, PNG, JPEG, and WebP may be rendered inline;
Office/text/CSV files download as attachments. Responses include `Cache-Control: private, no-store`,
`X-Content-Type-Options: nosniff`, and safe `Content-Disposition`. The service worker excludes all
`/api/*` requests, so previews, downloads, and uploads are never cached. Range requests are deferred.

Downloads and previews emit minimal audit events containing the Document/version identity, actor, and
timestamp. Upload audit records include safe MIME and byte size. Audit data never includes file
contents, object keys, signed URLs, provider credentials, or complete filenames.

## Links and UI

The workspace Document library supports source/visibility filtering, private upload, external reference,
template generation, metadata edits, version history, new-version upload, safe preview/download,
record linking, and archive. Existing typed links cover Artist, Booking, Call Sheet, Release, Campaign,
Travel, and Production. Contracts retain their separate explicit `ContractDocument` association; Rights
Works and Royalty Statements retain their existing source-document fields. Domain models are not merged
into Documents, and audio masters/large media asset management remain deferred.
