# Permissions

Django owns authorization. The global API default requires an authenticated user; each
future domain must define explicit permissions at its API boundary and enforce object-level
access where necessary. Hiding controls in the frontend is not authorization.

Roles, team boundaries, artist-level access, and elevated operations are intentionally not
invented in this foundation. They require a documented permissions matrix. Important
mutations must eventually write audit records that identify the actor, action, target, and
time without exposing sensitive values.
