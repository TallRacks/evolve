# Account Security

Django sessions remain the only browser authentication authority. Login, logout, password change, and password reauthentication require the existing same-origin CSRF protections. No JWT, Auth.js, browser authentication token, SSO provider, or second authentication authority is present.

`users.SecurityEvent` is an immutable, user-scoped authentication trail for successful and attributable failed logins, logout, reauthentication, and password changes. The user Security page exposes only its owner’s recent event type, outcome, time, bounded client description, and request IP. Passwords, hashes, cookies, CSRF values, and session identifiers are never recorded.

A successful password check writes a server timestamp into the Django session. Authenticated API requests reject password freshness at or beyond 14 days and direct the browser to `/reauthenticate`; successful reauthentication renews the timestamp. The browser clock is not trusted. The normal session remains browser-close with an eight-hour maximum, so password freshness is an independent upper bound and does not extend session lifetime.

SSO, SAML, OIDC, Google, and Microsoft Entra remain future work. Production login throttling is also a security follow-up; no homemade permanent account lockout was introduced.

## Provider network and secret trust

Provider records store constrained environment-variable names only. Storage endpoints must use HTTPS,
contain no embedded credentials, and resolve only to globally routable addresses, blocking loopback,
private, link-local, and cloud metadata targets. SMTP hosts may intentionally be private and therefore
remain an explicit platform-superuser network trust decision. Connection errors are reduced to safe
error classes; credential values, provider responses, and authorization material are excluded from
APIs, audit events, and logs.


Transactional email validates addresses, rejects sender/subject header newlines, escapes HTML content, verifies SMTP TLS certificates, and stores connector credentials only through external environment references. Delivery logs omit bodies, invitation tokens, cookies, and provider secrets. Email links do not bypass sign-in or resource authorization.

## Native and channel boundary

AI, web, PWA, WhatsApp, inbound email, and native mobile are clients of the same Django authorization boundary. Native credentials are not yet implemented and must use the reviewed Keychain/Keystore design before production. This phase does not alter migration history or deploy experimental mobile authentication.
