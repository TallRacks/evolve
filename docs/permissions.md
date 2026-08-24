# Permissions

Django owns authorization. Organization access is centralized in
`organizations.permissions`; selectors scope reads in `organizations.selectors`. Frontend
navigation and portal routes are user experience only and never security boundaries.

```text
platform superuser -> active organization -> allowed
normal user        -> active user + active organization + active membership
permission         -> access above + permission granted by membership role
staff only         -> no implicit organization access
anonymous          -> denied
```

The initial permission vocabulary is intentionally small: organization view/manage and
membership view/manage. Owner has all organization permissions; administrator manages the
organization and memberships; manager can view the organization and memberships; member and
artist can view the organization. Application code asks for permission identifiers rather
than comparing role names. Future organization-owned querysets must start from an authorized
organization selector, never an organization ID supplied by a client alone.

Reusable DRF permission classes live in `organizations.api.permissions` for authenticated
users, active organization access, platform superusers, and artist access. Artist portal
access is represented by the backend-derived `portal.artist` permission. Platform access
requires an active Django superuser; `is_staff` alone never qualifies.

Frontend guards provide loading, redirect, and 403 user experience only. They consume
backend-derived bootstrap data but do not protect backend resources. Every future
organization-owned endpoint must independently resolve an authorized organization and apply
the relevant backend permission.
