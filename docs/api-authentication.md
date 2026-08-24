# API-key authentication

An `APIClient` belongs to one organization and may own keys. New clients and keys require
`api.manage`. Creation returns a secret exactly once in the form `evolve_<prefix>_<random>`; only
the prefix and SHA-256 digest are stored. Normal API responses, Django admin, logs, and audit events
must never expose the raw secret or digest.

Send the secret using:

```http
Authorization: Bearer EVOLVE_API_KEY
```

Authentication rejects invalid secrets generically and rejects revoked or expired keys, inactive
clients, inactive organizations, and missing scopes. A successful request updates `last_used_at`.
A key can access only its client organization and cannot obtain platform authority. These keys do
not authenticate browser sessions and must never be put in localStorage or sessionStorage.

Client/key creation, key revocation, and client deactivation emit audit events containing only safe
identifiers or prefixes. Key recovery is impossible; create a replacement and revoke the old key.
