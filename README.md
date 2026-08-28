# Evolve v2

Private artist-management and operations platform. The repository contains the identity,
organization, white-label, artist, relationship, and booking foundations.

Milestone 14 adds a dedicated Finance domain for invoice snapshots, line items, recorded external
payments, allocations, currency-aware balances, authenticated print views, and scoped
workspace/platform/developer reads. See `docs/finance.md`.

## Prerequisites

- Docker Engine with Docker Compose
- Git

## Local development

From the repository root:

```bash
cp .env.example .env
```

Replace every placeholder in `.env` with a local-only value. Generate a Django key,
for example, with:

```bash
docker compose run --rm --no-deps backend python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Then start the stack:

```bash
docker compose up --build -d
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
```

Open:

- Frontend: http://127.0.0.1:3000
- API health: http://127.0.0.1:8000/api/health/
- Django admin: http://127.0.0.1:8000/admin/

Follow logs and stop the stack with:

```bash
docker compose logs -f backend frontend
docker compose down
```

PostgreSQL has no host-published port. The frontend and backend ports are bound only
to loopback for local development. In production, remove those `ports` mappings and
attach the containers to the private network used by the independently managed Caddy
instance; only Caddy publishes ports 80 and 443.

## Validation

```bash
docker compose config --quiet
docker compose build backend frontend
docker run --rm -e EVOLVE_ENV=test evolve-backend ruff check .
docker run --rm -e EVOLVE_ENV=test evolve-backend pytest
docker run --rm -e EVOLVE_ENV=test evolve-backend python manage.py check
docker run --rm -e EVOLVE_ENV=test evolve-backend python manage.py makemigrations --check --dry-run
docker run --rm evolve-frontend npm run lint
docker run --rm evolve-frontend npm run typecheck
docker run --rm -e NODE_ENV=production evolve-frontend npm run build
```

Architecture and operational notes live in [`docs/`](docs/).

## Production

The live deployment checkout is `/opt/evolve/app`, and the canonical origin is
https://evolve.nastycsa.com. Production uses `compose.production.yml`, external secrets at
`/opt/evolve/secrets/evolve.env`, the external `evolve_proxy` network, and the preserved
`evolve_postgres_data` volume. Exact deployment, migration, Caddy, validation, and rollback
commands are documented in [`docs/deployment.md`](docs/deployment.md).

## Identity foundation

Evolve uses the custom `users.User` model, Django sessions, organization-scoped memberships,
centralized backend permission helpers, and hashed seven-day invitations. Same-origin Django
session authentication is exposed through `/api/auth/csrf/`, `/api/auth/login/`,
`/api/auth/me/`, and `/api/auth/logout/`. Next.js provides the authenticated application
shells at `/dashboard`, `/platform`, `/workspace`, and `/artist`; Django administration
remains at `/admin/`.

See [`docs/identity-and-access.md`](docs/identity-and-access.md),
[`docs/authentication.md`](docs/authentication.md), and
[`docs/permissions.md`](docs/permissions.md).

Milestone 4 added the responsive application shell, organization-scoped team and invitation
management, organization settings, profile editing, platform organization/user views, and a
read-only audit log. See docs/portal-architecture.md and docs/team-management.md.

Milestone 5 adds organization branding, controlled custom-domain onboarding, and organization-scoped API credentials. See [`docs/white-label.md`](docs/white-label.md), [`docs/custom-domains.md`](docs/custom-domains.md), [`docs/api.md`](docs/api.md), and [`docs/api-authentication.md`](docs/api-authentication.md).

Milestone 6 introduces the first product domain: organization-owned Artist profiles, lifecycle,
artist-team responsibilities, optional portal-user links, workspace and platform administration,
an artist-aware portal, and a read-only `artist.read` integration API. Artist remains distinct
from User. See [`docs/artists.md`](docs/artists.md).

## Relationship management

Milestone 7 adds organization-scoped Promoter, Venue, and reusable business Contact master records. Workspace routes live under `/workspace/promoters`, `/workspace/venues`, and `/workspace/contacts`; platform-superuser views use the corresponding `/platform` routes. See `docs/promoters.md`, `docs/venues.md`, and `docs/contacts.md`.

## Booking management

Milestone 8 adds organization-scoped booking workflow, explicit status transitions, frozen partner/contact snapshots, team and contact assignments, permission-gated commercial terms, platform administration, dashboard metrics, and a read-only `booking.read` integration endpoint. See [`docs/bookings.md`](docs/bookings.md).

Milestone 9 adds one versioned Call Sheet per Booking, structured run-of-show and operational sections, atomic publication/superseding, immutable published history, print-friendly authenticated views, platform administration, and a curated `callsheet.read` integration endpoint. See [`docs/call-sheets.md`](docs/call-sheets.md).

## Music catalog

Milestone 10 adds organization-scoped Releases, reusable Tracks, ordered tracklists, descriptive credits, identifiers, release links, explicit release lifecycle, artist read-only catalog views, platform administration, and the `music.read` developer API. See [`docs/music.md`](docs/music.md).

## Campaign and rollout planning

Milestone 11 adds strategic Campaigns, planned channels, operational Rollouts, milestones, assigned tasks, dependencies, derived progress, artist/release views, platform administration, and the `campaign.read` integration scope. See [`docs/campaigns.md`](docs/campaigns.md) and [`docs/rollouts.md`](docs/rollouts.md).

## Milestone 12: Calendar and Documents

The unified calendar projects existing operational dates without duplicate rows. Standalone events and external-reference document metadata are available in workspace, platform, Artist portal, Django admin, and scoped developer APIs. Binary document upload remains disabled. See `docs/calendar.md` and `docs/documents.md`.

## Milestone 13: In-app notifications

Recipient-specific in-app notifications, preferences, inbox state, lifecycle integrations, and platform metadata oversight are implemented without external delivery infrastructure. See `docs/notifications.md`.

## Milestone 15: Rights and Royalties

Works, Rights Parties, Master/Publishing ownership, Royalty Statements, earnings allocations,
conservative Artist visibility, and rights.read integration summaries are implemented without
payout infrastructure. See docs/rights.md and docs/royalties.md.

Milestone 16 adds grouped workspace/platform navigation, a keyboard-accessible command palette, PostgreSQL-backed Global Search, a curated role-aware dashboard, and a permission-scoped Artist 360 overview. See `docs/navigation.md` and `docs/search.md`.

Milestone 17 adds organization-scoped Travel itineraries, travellers, ordered transport, accommodation and room assignments, Booking and Call Sheet workflows, Calendar and Document integration, a read-only Artist itinerary, platform administration, and the conservative `travel.read` developer API. See `docs/travel.md`.

## Production advancing

Milestone 18 adds the organization-scoped Production Advance workflow at `/workspace/production`, the curated Artist view at `/artist/production`, and platform oversight at `/platform/production`. See `docs/production.md` for lifecycle, privacy, Call Sheet snapshot, and integration rules.


## Contracts

Milestone 19 adds organization-scoped Contract lifecycle, parties, terms, sections, approvals, manual signing status, Booking and Document links, Artist-safe views, platform oversight, and the `contract.read` API scope. See `docs/contracts.md`.

## Milestone 21: Workflow automation and templates

Evolve now includes reusable Tasks and checklists, Release task progress, the Notifications and curated Activity hubs, immutable account Security Events with explicit 14-day password freshness, transactional Booking operational setup, automatic draft Call Sheet source snapshots, and safe backend-managed document templates. See [`docs/tasks.md`](docs/tasks.md), [`docs/security.md`](docs/security.md), and [`docs/document-templates.md`](docs/document-templates.md).

## Milestone 22 workspaces

- `/dashboard` is the single context-aware dashboard; `/platform` redirects there.
- `/workspace/reports` provides permission-filtered reports, private saved views, and safe CSV.
- `/platform/connectors/email` and `/platform/storage` manage superuser-only provider metadata.
- Provider credentials are provisioned as external `EVOLVE_...` environment secrets; the UI stores references only.

See `docs/reporting.md`, `docs/email-connectors.md`, `docs/storage.md`, and `docs/navigation.md`.
