# Workspace scoping registry

Organization is the tenancy and security boundary. Workspace is an operational grouping and never grants organization access.

| Area | Classification | Enforcement |
| --- | --- | --- |
| Workspace Home / Summary | WORKSPACE_SCOPED | Authorized Workspace endpoint; Boards, Office Documents, and Tasks with explicit source-Document Workspace links. |
| Persistent Boards | WORKSPACE_SCOPED | Workspace-owned Board query and detail authorization. |
| Operational task board | WORKSPACE_SCOPED when selected | `workspace_id` filters only tasks with a source Document in that Workspace. |
| Office / Documents | WORKSPACE_SCOPED when selected | `Document.workspace` filter; global views remain organization scoped. |
| Tasks / My Work | ORGANIZATION_SCOPED by default; explicit Workspace filter | Assignee does not imply Workspace. Optional filter uses explicit source-document linkage. |
| Dashboard | ORGANIZATION_SCOPED | Unchanged by Workspace selection. |
| Artists, Promoters, Venues, Contacts, Bookings, Releases | ORGANIZATION_SCOPED | Master records are not silently filtered. Workspace projections require explicit relationships. |
| Calendar, Finance, Contracts, Rights, Royalties | ORGANIZATION_SCOPED | Existing domain authorization remains authoritative. |
| Automations | ORGANIZATION_SCOPED | Current model has no Workspace relation. |
| Platform administration | PLATFORM_GLOBAL | Existing superuser-only behavior. |

## Stale selection and lifecycle

The selector stores UX state in the session only; every API request revalidates the
organization and Workspace. Organization changes clear the Workspace first. The
active Workspace list excludes archived Workspaces, so a revoked, deleted, or
archived selection falls back to another active Workspace or clears safely. Detail
reads may still show an archived Workspace to an authorized member. New Office
documents reject archived Workspaces. No arbitrary UUID, stale session value, or
`is_staff` flag grants access.

No Workspace foreign key was added to Tasks, Bookings, or Releases: Tasks inherit
Workspace context only through their explicit source Document, while Booking and
Release master data remains organization-wide until a domain relationship is
introduced deliberately.
