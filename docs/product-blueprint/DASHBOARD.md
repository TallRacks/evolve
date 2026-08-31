# Dashboard Command Centre

The workspace dashboard is a permission-scoped consolidation surface. Django derives all counts and attention items after organization authorization; React does not infer access from navigation.

## Implemented layout

- High-value KPI strip: upcoming Bookings, active Artists, open Tasks, and Needs Attention.
- Needs Attention feed capped at 12 actionable records with severity, domain, reason, date, and stable deep link.
- Today feed for Bookings and due Tasks.
- Permission-aware Create menu, assigned work, recent Activity, and upcoming Bookings.
- Structural loading skeletons that do not expose protected content.

Signals are independently permission gated for Bookings, Tasks, Production, Travel, Contracts, Finance, Music, Rollouts, and Rights. Finance and Rights information is absent without the relevant permission. Monetary values are not aggregated.
