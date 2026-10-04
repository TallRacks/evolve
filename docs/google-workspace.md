# Google Workspace integration foundation

Google-native content remains edited and owned in Google. Evolve stores only safe metadata and an entity link; it does not embed or clone Google Docs/Sheets.

The planned connection is organization-scoped and user-owned, with OAuth state/CSRF validation, narrow scopes (prefer `drive.file`), and access/refresh token references resolved through the existing external-secret convention. Raw OAuth tokens, authorization codes, Drive contents, and broad Drive enumeration are not stored in ordinary Evolve fields.

Planned actions are create Google Doc, create Google Sheet, link an existing file, open/edit in Google, refresh metadata, and save an authorized snapshot to Evolve. These remain disabled while the provider is Not Configured; CI uses mocked provider responses only.

The current web surface is intentionally an honest configuration state at `/platform/google-workspace`. Enabling it requires OAuth client ownership, redirect URI review, secret provisioning, privacy review, and a separate production migration/reconciliation decision if connection metadata is persisted.

## Gmail Pub/Sub inbound notifications

Gmail push notifications can trigger the existing scoped OAuth2 IMAP sync. The Pub/Sub body contains only the Gmail mailbox address and history ID; Evolve does not store message content in Pub/Sub.

Set a long random server-side token in the production environment:

EVOLVE_GMAIL_PUBSUB_TOKEN=<long-random-token>

For an organization-owned email messaging connector, use this push URL:

https://evolve.nastycsa.com/api/messaging/webhooks/gmail/<MESSAGING_CONNECTOR_UUID>/?token=<same-token>

The connector must be organization-owned and active. The matching OAuth2 IMAP connector must also be assigned to that same organization and inbound connector. Push requests without the token are rejected. The handler triggers the existing deduplicated IMAP sync; it does not broaden mailbox access.
\nTo register or renew the Gmail watch after assigning the OAuth2 IMAP connector, call the authenticated endpoint:\n\nPOST /api/workspace/mailbox/gmail/watch/\n\nSend organization_id, the organization-owned messaging connector_id, and topic_name set to projects/PROJECT_ID/topics/TOPIC_ID. Optionally include sender_connector_id or mailbox_address. The endpoint exchanges the configured refresh token, registers the Gmail watch, and stores only the topic, history ID, and expiration metadata. The Pub/Sub push URL remains the webhook URL above.\n