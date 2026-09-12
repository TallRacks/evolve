# Transactional email delivery

Email is a delivery channel for selected Notification events, not a second event or authorization source. The initial policy covers organization invitations, task assignment/reassignment, Contract approval requests, and published Call Sheets. Finance distribution, external contacts, marketing, password-change mail, and bulk mail are not implemented.

Delivery is synchronous after transaction.on_commit(). A provider failure cannot roll back the business mutation or its in-app notification. There is no automatic retry; platform superusers may explicitly retry failed or not-configured notification attempts. A future background worker may replace the synchronous adapter without changing the event or authorization boundary.

EmailDeliveryAttempt is append-only and records pending, sent, failed, skipped, not-configured, or suppressed. Sent means the configured SMTP server accepted the message, not that the recipient received it. Logs store recipient and subject snapshots but no body, SMTP password, invitation token, cookie, or provider secret. Generic audit records are used only for explicit retries.

Templates are code-defined, have plain-text and escaped HTML alternatives, and use a small email-safe shell. Bodies include sparse operational context and an authenticated deep link, never contract text, commercial values, private notes, or broad recipient data. There are no tracking pixels, click tracking, open tracking, unsubscribe machinery, or remote analytics.

Organization display name, HTTPS logo, and primary color may brand a message. Links prefer an active, verified primary organization domain and otherwise use EVOLVE_APP_ORIGIN. This does not relax the authorization required after sign-in. Sender and reply-to addresses always come from the selected platform connector.

Category preferences control in-app and email channels independently. Conservative email defaults enable Tasks & team, Call Sheets, and Contracts; high-volume categories default off. Security preferences are reserved and cannot be disabled, although password/security email events are deferred.
