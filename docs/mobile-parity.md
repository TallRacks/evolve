# Native mobile parity manifest

Native support is intentionally operational rather than administrative. All
rows use Django APIs and the same permissions as web.

| Domain | Native status | Initial capability |
|---|---|---|
| Home / My Work / Inbox | READ/OPERATE | today, tasks, approvals, mentions, notifications, confirmations |
| Tasks | READ/OPERATE | list, detail, create/edit/assign/status/complete when authorized |
| Artists | READ/OPERATE | list and 360 detail |
| Bookings | READ/OPERATE | queue, detail, readiness, operations, call-sheet links |
| Call Sheets | READ/OPERATE | published operational viewer; controlled draft actions later |
| Calendar / Notifications | READ/OPERATE | authorized list and deep links |
| Production / Travel | READ/OPERATE | operational summaries and checklists |
| Releases / Tracks / Campaigns / Rollouts | READ/OPERATE | operational records and tasks |
| Documents | READ ONLY | metadata and authorized download/picker integration later |
| Finance | READ ONLY | safe summaries, invoices, payment status |
| Rights / Royalties | READ ONLY | operational summaries only |
| Contracts / Approvals | READ/OPERATE | status, pending approvals, authorized decisions |
| Copilot | READ/OPERATE | same Action Gateway and confirmation policy |
| Admin / Platform / Developer | WEB ONLY FOR NOW | web is the controlled administration surface |
| Authentication | FUTURE | pending approved native credential design |

The manifest at `mobile/feature-manifest.json` is checked in and is the source
for native route regression checks. Android remains a supported architecture;
iOS/App Store is the first distribution target.

Documents are intentionally web-first in the initial native screen set: the
native plan is metadata, authorized open/download, and later secure device
picker upload after mobile API authentication is fully validated.
