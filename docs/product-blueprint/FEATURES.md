# Evolve Feature Map

This map reflects the source at the Milestone 22 baseline and the shared experience refinement.

| Feature | Route family | Backend | Readiness | Classification |
| --- | --- | --- | --- | --- |
| Identity and sessions | `/login`, `/profile` | `users` | Operational | KEEP |
| Organizations and team | `/workspace/organization`, `/workspace/team` | `organizations` | Operational | KEEP |
| Artists and Artist 360 | `/workspace/artists` | `artists` | Operational | POLISH |
| Bookings and call sheets | `/workspace/bookings`, `/workspace/call-sheets` | `bookings`, `callsheets` | Operational | POLISH |
| Promoters, venues, contacts | workspace relationship routes | respective apps | Operational | KEEP |
| Music, campaigns, rollouts | workspace music/campaign routes | `music`, `campaigns` | Operational | KEEP |
| Calendar and documents | `/workspace/calendar`, `/workspace/documents` | `calendar_app`, `documents` | Operational | POLISH |
| Notifications and activity | notification/activity routes | `notifications`, `audit` | Operational | KEEP |
| Finance, rights, royalties | finance/rights/royalties routes | `finance`, `rights` | Operational | KEEP |
| Travel and production | travel/production routes | `travel`, `production` | Operational | KEEP |
| Contracts | `/workspace/contracts` | `contracts` | Operational | KEEP |
| Tasks and templates | tasks/template routes | `tasks`, `documents` | Operational | KEEP |
| Reporting | `/workspace/reports` | `reporting` | Operational | KEEP |
| Platform administration | `/platform/*`, `/admin/*` | domain APIs, Unfold | Operational | KEEP |
| Developer API | `/developer/*` | scoped developer APIs | Operational | KEEP |
| PWA lifecycle | manifest, service worker, offline route | frontend only | Foundation | EXTEND |

No domain, model, or route is deprecated by this refinement.
