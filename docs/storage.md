# Storage Providers

Evolve reuses the `integrations.StorageProvider` configuration for private Document objects. Provider
rows contain endpoint, region, bucket, prefix, lifecycle status, and names of `EVOLVE_STORAGE_*`
environment variables. Access-key and secret-key values remain in external server secrets and are never
stored in PostgreSQL, serializers, audit events, logs, or browser state. Rotating an external secret
value does not modify Document rows.

Uploads require one active default provider with both referenced secrets present. There is no fallback
to a public directory or local web-served filesystem. Production remains deliberately unconfigured
until an approved bucket and credentials are supplied; the upload UI reports that state and external
references/generated documents continue to work.

Objects are uploaded privately with server-generated keys. Each stored Document retains its provider
foreign key, so changing the default affects future uploads only. Deactivating a provider prevents new
uploads through it but does not reinterpret or remove existing objects; existing reads use the retained
provider reference. `PROTECT` prevents deleting a referenced provider configuration. Platform storage
cards show Evolve-managed object count and bytes from Document metadata without listing the bucket.

The controlled provider test writes, reads, and deletes a small random probe object. It creates no
Document row. Provider failures return sanitized unavailable responses; internal credentials, endpoints,
keys, and SDK errors are not sent to clients. A failed upload does not create available metadata, and a
best-effort delete removes an object if the metadata transaction fails.

Storage buckets must remain private. Public ACLs and permanent public URLs are unsupported. Full bucket
reconciliation, automatic migration, lifecycle purge, restore, legal hold, antivirus scanning, OCR,
and public sharing are deferred.
