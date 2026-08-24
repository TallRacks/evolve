# Identity and Access

## Relationships

```text
User --< Membership >-- Organization
               |
               +-- role (one role per membership for now)

Organization --< Invitation >-- intended email and role
User -----------^ invited_by / accepted identity
```

`User` is the project identity model and uses a UUID primary key plus normalized unique email
for login. It is deliberately separate from the future Artist domain entity.

`Organization` is the primary ownership and authorization boundary. A user has at most one
membership per organization. Active users with active memberships in active organizations
receive the permissions associated with their membership role. Portal URLs are presentation
boundaries only; Django must enforce every organization boundary.

The initial roles are `owner`, `admin`, `manager`, `member`, and `artist`. Permission checks
use centralized permission identifiers rather than role comparisons in views. Multiple owner
memberships are permitted. One role belongs to each membership for now.

Django superusers are platform superusers and may cross organization boundaries. `is_staff`
only permits Django admin login and never grants organization access. Identity and
organization administration screens are restricted to platform superusers.

## Invitations

Invitation tokens use Python's cryptographically secure token generator. PostgreSQL stores
only a SHA-256 digest; the raw token is returned once by the creation service for future
delivery. Invitations expire exactly seven days after server-side creation. Acceptance checks
the token, expiry, revocation, replay, active organization, and normalized user email inside a
transaction. Creating a replacement invitation revokes any prior unexpired invitation for the
same organization and email. Email delivery is not part of this milestone.

## Decisions Deferred

- Whether memberships eventually support multiple roles
- Advanced owner transfer and removal rules
- Initial organization bootstrap UX
- Exact long-term session duration and reauthentication policy
- Final MFA enforcement policy
- Artist portal membership behavior
- Future SSO providers
