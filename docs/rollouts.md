# Rollouts

Rollout is the operational execution plan under a Campaign. It contains ordered milestones, actionable tasks, and same-rollout task dependencies without duplicating Campaign strategy.

## Execution model

Rollout lifecycle is draft to active/cancelled, active to completed/cancelled, and completed/cancelled to archived. Milestones group tasks but are not templates. Tasks use explicit todo, in-progress, blocked, done, and cancelled states. Completion is a dedicated service that records timestamp and actor. Authorized users may explicitly reopen done tasks to todo or in-progress, clearing completion metadata and writing an audit event.

Campaign, Rollout, milestone, task, and Membership relationships preserve organization scope. Owners and assignees must be active Memberships with active Users. Dependencies reject duplicates, self-links, cross-rollout links, and graph cycles.

Progress is derived, never stored: done non-cancelled tasks divided by all non-cancelled tasks, with zero tasks reported as zero percent. Overdue state is derived from due date and current task status.

## Access and future projections

Workspace execution is `/workspace/rollouts/[id]`; platform inventory/detail is `/platform/rollouts` and `/platform/rollouts/[id]`. Permissions are `rollout.view`, `rollout.manage`, and `rollout.task.manage`. Important Rollout, milestone, task, completion, reopen, cancellation, and dependency changes are audited.

`campaign.read` integration clients may call `/api/developer/rollouts/` for curated plan summaries and computed progress. Task detail, internal descriptions, assignee contact information, and audit data are excluded.

A future Calendar should be a read projection over Bookings, Releases, Campaign dates, Rollout task due dates, and Call Sheets, not duplicated calendar tables. Future Notifications may consume approaching/overdue task dates and lifecycle audit events. No Redis, Celery, or notification delivery is introduced.
