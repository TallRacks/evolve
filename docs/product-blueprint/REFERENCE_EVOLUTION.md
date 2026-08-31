# Reference Evolution

| Original reference capability | Current Evolve implementation | Improvement / architecture difference | Status |
| --- | --- | --- | --- |
| Dashboard KPI cards | Permission-scoped KPI strip, Today, My Work, Activity | Django-derived data; no client-trusted authorization | Improved |
| Needs Attention | Capped cross-domain backend feed with deep links | Each domain independently permission gated | Implemented |
| Booking priority queue | 30-day P1-P4 queue, Days Out, readiness | Derived values; existing lifecycle preserved | Improved |
| Booking month grouping | Native collapsible month groups | Responsive card/table treatment | Implemented |
| Contract risk | Upcoming contract workflow signals and permission-aware readiness | No simplistic payment-to-contract inference | Intentionally different |
| Call Sheet editor/print | Existing versioned editor, review, publish, print | Published history immutable; no server PDF | Implemented |
| Call Sheet section ordering | No persisted custom section order | Avoided speculative schema in this phase | Deferred |
| Music pipeline | Release countdown, task progress, campaign state | Internal serializer prevents Artist/developer leakage | Implemented |
| Release deliverables | Existing generic Task/checklist workflow | No universal legal template imposed | Intentionally different |
| Rollout execution | Milestones, dependencies, priorities, owners, due dates, completion | Critical means operational risk, not CPM mathematics | Implemented |
| Campaign responsibility matrix | Phase-level Lead/Support Membership assignments | Same-organization validation, audit, no permission grant | Improved |
| Consolidated calendar | Existing projected Calendar with filters and source deep links | Source domains remain authoritative | Implemented |
| Team operations | Existing Membership, access, assignment, and workload views | No employee ranking or surveillance | Intentionally different |
| Skeletons and feedback | Dashboard/Booking/Campaign skeletons plus existing mutation notices | Protected data is never used as a loading placeholder | Improved |
| Offline application | Reachability state machine and static offline shell | No private response caching or offline mutation replay | Improved |
