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
