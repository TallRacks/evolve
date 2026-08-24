# Team Management

Organization access is modeled by one membership per user and organization. Active
membership, user, and organization status are all required. Roles use centralized permission
identifiers rather than view-level role comparisons.

Owners and administrators can create or revoke invitations and update membership role or
active state. Managers can inspect team and invitations. The final active owner is protected.
Deactivation removes organization access without deleting the user.

Invitations last seven days. Only a SHA-256 digest is stored. A generated raw token is
returned once for out-of-band delivery because no email provider exists. Acceptance requires
authentication with the intended email and is transactional and replay-safe.

Organization, membership, invitation, profile, and platform user mutations are audited.
Audit events are read-only and omit all secret material.

Owner-impacting API and Django admin changes use the same domain validators. These changes
run in database transactions and lock the affected organization rows before validating the
canonical effective-owner queryset, serializing concurrent owner demotions and user
deactivations. Destructive deletion remains disabled for users, memberships, and organizations.
