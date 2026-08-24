# Authentication

Django is the authentication authority. The same-origin browser architecture uses Django
sessions and CSRF protection through `https://evolve.nastycsa.com`; JWT and Auth.js are not
used. `/api/auth/me/` exposes safe identity and active-membership data for an authenticated
session and returns 401 otherwise. The web lifecycle is:

```text
GET /api/auth/csrf/ -> CSRF cookie
POST /api/auth/login/ -> authenticated Django session and bootstrap response
GET /api/auth/me/ -> refresh safe bootstrap data
POST /api/auth/logout/ -> invalidate the current session
```

Login accepts email and password, uses Django authentication, rotates the session through
Django's login function, and returns the same safe bootstrap shape as `/api/auth/me/`.
Invalid, unknown, and inactive accounts receive the same generic error. Logout requires an
authenticated session and flushes it.

Production cookies are HttpOnly, Secure, and SameSite=Lax. Sessions currently last at most
eight hours and expire when the browser closes. Django stores sessions server-side, allowing
server-side invalidation. Advanced device management, remember-me, concurrent-session limits,
and forced periodic reauthentication are deferred.

Passwords use Django's standard hashers and validation framework: user similarity checks, a
12-character minimum, common-password rejection, and numeric-only rejection. Password expiry
and custom cryptography are intentionally excluded.

## CSRF strategy

The frontend first requests `/api/auth/csrf/`, which sets Django's readable CSRF cookie.
State-changing requests send that value in `X-CSRFToken` and include same-origin cookies.
The session cookie remains HttpOnly. Login is explicitly protected with Django
`csrf_protect`; logout is protected by DRF session authentication. No endpoint is exempted.

## Deferred Authentication Features

- Password reset
- Password change UI
- Account creation for invited emails that do not yet have an Evolve user
- MFA, including TOTP, recovery codes, and possible passkeys
- SSO
- Device and session management
- Remember-me
- Forced reauthentication
