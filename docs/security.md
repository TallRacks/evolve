# Account Security

Django sessions remain the only browser authentication authority. Login, logout, password change, and password reauthentication require the existing same-origin CSRF protections. No JWT, Auth.js, browser authentication token, SSO provider, or second authentication authority is present.

`users.SecurityEvent` is an immutable, user-scoped authentication trail for successful and attributable failed logins, logout, reauthentication, and password changes. The user Security page exposes only its owner’s recent event type, outcome, time, bounded client description, and request IP. Passwords, hashes, cookies, CSRF values, and session identifiers are never recorded.

A successful password check writes a server timestamp into the Django session. Authenticated API requests reject password freshness at or beyond 14 days and direct the browser to `/reauthenticate`; successful reauthentication renews the timestamp. The browser clock is not trusted. The normal session remains browser-close with an eight-hour maximum, so password freshness is an independent upper bound and does not extend session lifetime.

SSO, SAML, OIDC, Google, and Microsoft Entra remain future work. Production login throttling is also a security follow-up; no homemade permanent account lockout was introduced.
