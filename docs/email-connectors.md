# Email Connectors

Email connectors are platform-superuser configuration records. Evolve stores SMTP metadata and an
`EVOLVE_...` environment-variable reference, never the password or API token. Secret provisioning
remains an external deployment operation; the browser cannot read or edit environment files.

SMTP supports explicit TLS or implicit SSL, not both. Test Connection authenticates synchronously;
Send Test Email sends one controlled system message to the explicitly entered recipient. These
operations are audited without credentials or message bodies. A successful test is configuration
health at that moment, not delivery monitoring.

SMTP endpoints are a platform-administrator network trust decision because legitimate private SMTP
relays may be required. Configuration is therefore superuser-only. SPF, DKIM, DMARC, and sending-domain
authorization remain external DNS/provider responsibilities. Automatic notification email and provider
APIs remain deferred.
