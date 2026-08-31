# Evolve Storage Architecture

PostgreSQL stores application records through Django only. Binary Document objects use the configured
private S3-compatible `StorageProvider`; provider credentials remain external environment secrets.
Django is the sole authorization and streaming boundary, and no browser receives an object key,
credential, or permanent public URL.

Documents distinguish external references, generated text snapshots, and stored binaries. Stored rows
retain their provider, random organization/document/version-scoped key, normalized display filename,
detected MIME type, size, SHA-256 checksum, storage status, and upload timestamp. A changed default
provider applies only to future uploads. Archive retains historical objects; deletion and retention
policy are deliberate future work.

Allowed uploads are PDF, DOCX, XLSX, PPTX, CSV, UTF-8 text, PNG, JPEG, and WebP up to the configured
limit. Extension, signature/content, filename, and path validation are enforced by Django. HTML, SVG,
scripts, executables, malformed Office archives, and identity-document travel uploads are rejected.
This validation does not constitute malware scanning.

Downloads and inline PDF/image previews are session-authorized Django streams with private no-store and
nosniff headers. Domain and organization permissions are evaluated for direct URLs. The service worker
never handles `/api/*` or `/admin/*`, so it cannot cache private content or upload responses.
