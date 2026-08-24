# Authentication

Django is the authentication authority. The same-origin browser architecture uses Django
sessions and CSRF protection through `https://evolve.nastycsa.com`; JWT and Auth.js are not
used. `/api/auth/me/` exposes safe identity and active-membership data for an authenticated
session and returns 401 otherwise.

Production cookies are HttpOnly, Secure, and SameSite=Lax. Sessions currently last at most
eight hours and expire when the browser closes. Django stores sessions server-side, allowing
server-side invalidation. Advanced device management, remember-me, concurrent-session limits,
and forced periodic reauthentication are deferred.

Passwords use Django's standard hashers and validation framework: user similarity checks, a
12-character minimum, common-password rejection, and numeric-only rejection. Password expiry
and custom cryptography are intentionally excluded.

MFA is not implemented yet. The future direction should support TOTP, recovery codes, and
potential WebAuthn/passkeys without changing Django's identity authority.
