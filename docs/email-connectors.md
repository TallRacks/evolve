# Email connectors

Email connectors are platform-superuser configuration records. Evolve stores SMTP host, port, sender identity, transport mode, username, and an EVOLVE_EMAIL_ environment-variable reference. The referenced password remains external and is never returned by an API or stored in the database.

Exactly one active default connector is used for application mail. TLS certificate verification remains enabled. STARTTLS and implicit SSL are mutually exclusive. Sender names and subjects reject newline injection. Test Connection and Send Test Email are explicit platform operations; transactional delivery uses the same transport after a business transaction commits.

The platform delivery view reports attempt status and permits explicit retries of failed or not-configured notification attempts. SMTP sent means accepted by the SMTP server, not delivered to an inbox. Evolve does not automate bounce, complaint, open, or click tracking.

SPF, DKIM, DMARC, mail-domain authorization, reputation, and provider credentials must be configured externally. Production may remain honestly unconfigured: mutations and in-app notifications still succeed and attempts are recorded as not_configured.
