# Email connectors

Email connectors are platform-superuser configuration records. Evolve stores SMTP host, port, sender identity, transport mode, username, and a secret reference. The referenced password remains external and is never returned by an API or stored in the database.

The dashboard supports three secret backends: an environment reference (`EVOLVE_EMAIL_...`), HashiCorp Vault, and AWS Secrets Manager. Vault and AWS references use `path#key`, for example `secret/data/evolve/email#password` for Vault KV v2 or `evolve/production/email#password` for an AWS JSON `SecretString`. The backend needs `EVOLVE_VAULT_ADDR` and `EVOLVE_VAULT_TOKEN` for Vault, or the standard AWS SDK credential chain plus `AWS_REGION` for AWS. These runtime credentials are configured outside Git.

Exactly one active default connector is used for application mail. TLS certificate verification remains enabled. STARTTLS and implicit SSL are mutually exclusive. Sender names and subjects reject newline injection. Test Connection and Send Test Email are explicit platform operations; transactional delivery uses the same transport after a business transaction commits.

The platform delivery view reports attempt status and permits explicit retries of failed or not-configured notification attempts. SMTP sent means accepted by the SMTP server, not delivered to an inbox. Evolve does not automate bounce, complaint, open, or click tracking.

SPF, DKIM, DMARC, mail-domain authorization, reputation, and provider credentials must be configured externally. Production may remain honestly unconfigured: mutations and in-app notifications still succeed and attempts are recorded as not_configured.
