# Documents

Documents are organization-owned metadata records. Milestone 12 does not accept binary uploads and does not claim vault, encryption-at-rest, or malware-scanning capabilities. An HTTPS external reference is required; storage keys and checksums remain unavailable until durable private storage is selected.

## Model and links

`Document` uses UUID identity, explicit version lineage, visibility, archive lifecycle, and external file metadata. Versions are new immutable references in a root lineage; an existing reference is never silently overwritten. `DocumentLink` uses explicit nullable foreign keys to Artist, Booking, CallSheet, Release, or Campaign with a database check requiring exactly one target and service/model validation requiring the same organization. No unrestricted generic foreign key exists.

## Access

- `ORGANIZATION`: authorized members with `document.view`.
- `ARTIST`: linked Artist portal users for an attached Artist; organization access remains backend authorized.
- `RESTRICTED`: requires `document.restricted.view` or platform superuser.
- `document.manage` controls metadata, versions, links, and archive operations. Staff status alone grants nothing.

Identification/passport material, passwords, API secrets, card data, private keys, executables, and other sensitive identity files are unsupported. Ordinary workflows archive metadata; physical deletion is deferred.

## APIs and storage

Workspace, platform, Artist portal, and `document.read` developer APIs expose curated metadata. The developer API excludes restricted/Artist documents and all download URLs. `documents.storage` is the single future storage interface; S3-compatible provider selection, signed downloads, upload allowlists, checksum generation, malware scanning, OCR, public sharing, PDF generation, and e-signatures are deferred.
