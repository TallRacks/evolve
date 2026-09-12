# Native mobile authentication threat model

## Boundary

Browser clients continue using Django sessions, HttpOnly/SameSite cookies, CSRF,
and the existing 14-day password-freshness policy. Native clients use a separate
Bearer credential accepted only by `MobileOpaqueAuthentication`. Both paths
resolve the same User and active organization memberships; credentials never
contain permissions or organization claims.

## Credential lifecycle

Login validates email/password through Django, creates a revocable device record,
and returns a 15-minute access credential plus a 14-day refresh credential.
Only SHA-256 digests are stored. Raw values are returned once and are never
written to logs, URLs, query strings, AsyncStorage, SQLite, or database fields.

Every refresh is row-locked and rotates the old refresh credential. A rotated
refresh credential is rejected; detected reuse revokes the entire device. Logout
revokes the current device, while logout-all revokes every native device. Access
requests require an active user, active device, unexpired credential, and current
server-side authorization. Password changes and deactivation must revoke native
credentials before production release; membership changes are reflected by
normal permission checks.

## Threats and controls

- Token theft: short access lifetime, hashed storage, TLS, rotation, and revocation.
- Lost/stolen phone: revoke one device from account security or revoke all devices.
- Replay: digest lookup, expiry, row lock, one-use refresh rotation, reuse detection.
- Organization escalation: no token claims; every API selector checks membership.
- Staff bypass: native authentication supplies identity only; existing permissions apply.
- Deep-link abuse: route identifiers are untrusted and are authorized after navigation.
- Error leakage: clients receive normalized safe errors; credentials are never echoed.
- Browser regression: native endpoints do not change session or CSRF endpoints.

SecureStore is the only intended native credential storage: iOS Keychain and
Android Keystore-backed Expo SecureStore. No analytics, crash SDK, or local
credential logging is used. JWT was rejected because server-side opaque records
provide simpler revocation, rotation, and device control without duplicating
authorization claims.

This implementation is not production-approved until threat-model review,
password/deactivation revocation hooks, migration validation on fresh and
reconciled databases, and security tests pass.
