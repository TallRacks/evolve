# Google Workspace integration foundation

Google-native content remains edited and owned in Google. Evolve stores only safe metadata and an entity link; it does not embed or clone Google Docs/Sheets.

The planned connection is organization-scoped and user-owned, with OAuth state/CSRF validation, narrow scopes (prefer `drive.file`), and access/refresh token references resolved through the existing external-secret convention. Raw OAuth tokens, authorization codes, Drive contents, and broad Drive enumeration are not stored in ordinary Evolve fields.

Planned actions are create Google Doc, create Google Sheet, link an existing file, open/edit in Google, refresh metadata, and save an authorized snapshot to Evolve. These remain disabled while the provider is Not Configured; CI uses mocked provider responses only.

The current web surface is intentionally an honest configuration state at `/platform/google-workspace`. Enabling it requires OAuth client ownership, redirect URI review, secret provisioning, privacy review, and a separate production migration/reconciliation decision if connection metadata is persisted.
