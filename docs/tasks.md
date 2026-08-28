# Tasks and Checklists

`tasks.Task` is organization-owned operational work. It supports explicit nullable links to Artist, Booking, Release, Campaign, Rollout, Production Advance, Travel Itinerary, and Contract; it does not use a generic foreign key. Protected source permissions continue to control visibility.

Statuses are `todo`, `in_progress`, `blocked`, `done`, and `cancelled`. Lifecycle changes use the task service so completion actor/time, audit events, and sparse assignee notifications remain consistent. Priority is `low`, `normal`, `high`, or `urgent`. Overdue and checklist progress are derived at read time.

A `TaskChecklistItem` is a sub-step, not a Task. Completion metadata is server-managed and removal is semantic. Release detail uses ordinary Tasks linked through the typed Release relation. RolloutTask and Production Advance checklist records remain domain-specific and are not rewritten by this feature.

Owners, administrators, and managers can manage Tasks under the centralized organization policy. Members can view permitted Tasks. Platform superusers retain explicit cross-organization access; `is_staff` alone grants nothing.

Task activity is the curated Task subset of immutable AuditEvent data. Comments are deferred because the milestone does not require a separate chat or discussion model.
