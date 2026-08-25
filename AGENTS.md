# Evolve v2 Engineering Instructions

## Scope

Evolve is a private artist-management and operations platform. Keep changes small,
reviewable, and within the requested domain. Do not create product modules before
their requirements are defined.

## Fixed architecture

- Frontend: Next.js, React, TypeScript, Tailwind CSS, and shadcn/ui.
- Backend: Python, Django, Django REST Framework, and Django Unfold.
- Database: PostgreSQL.
- Infrastructure: Docker, Docker Compose, Caddy, and Ubuntu 24.04.
- Repository: monorepo with `frontend/`, `backend/`, `infrastructure/`, and `docs/`.

## Architectural rules

1. The browser/frontend must never connect directly to PostgreSQL.
2. All database access goes through Django.
3. Django is the source of truth for authentication, authorization, and business logic.
4. Important mutations must eventually produce audit-log entries.
5. Database schema changes must use Django migrations.
6. Secrets must never be committed.
7. PostgreSQL, Django, and Next.js must not publish ports publicly in production.
8. Only Caddy exposes ports 80 and 443 in production.
9. Keep modules and domain logic separated.
10. Do not introduce Redis, Celery, microservices, or other infrastructure until required.
11. Do not suppress TypeScript, Python, linting, or type errors to make builds pass.
12. Prefer small, reviewable implementations.

## Coding conventions

- Put Django project configuration in `backend/config/` and shared primitives in
  `backend/core/`. Give each future business domain its own Django app.
- Keep business rules out of views, serializers, templates, and React components.
- Use environment variables for secrets, credentials, hosts, and environment-specific
  settings. Update `.env.example` when adding a required variable.
- Use Django ORM and migrations for persistence. Never execute database queries from
  the frontend.
- Keep API endpoints under `/api/`. Use explicit serializers and permission classes.
- Use strict TypeScript. Prefer server components unless browser interactivity requires
  a client component.
- Reuse shadcn/ui primitives and project design tokens rather than creating parallel
  component systems.
- Format Python with Ruff and frontend code with the configured ESLint rules.
- Add concise comments only when intent cannot be made clear through names and structure.

## Testing and validation

- Add or update focused tests with each behavior change.
- Backend changes must pass `ruff check`, `pytest`, and `manage.py check`.
- Model changes must include migrations and pass `manage.py makemigrations --check`.
- Frontend changes must pass `npm run lint`, `npm run typecheck`, and `npm run build`.
- Integration/configuration changes should also pass `docker compose config` and
  relevant container health checks.
- Do not weaken tests, checks, or compiler settings to obtain a passing result.

## Git and security

- Do not commit generated dependencies, build output, local databases, environment
  files, credentials, private keys, or production data.
- Do not commit or push unless explicitly asked.
- Preserve unrelated work in a dirty worktree.

## Production deployment

- The canonical public origin is `https://evolve.nastycsa.com`.
- The deployment checkout is `/opt/evolve/app`.
- Production secrets live outside Git at `/opt/evolve/secrets/evolve.env` with mode `600`.
- Caddy is independently managed from `/opt/evolve/infrastructure/caddy`; do not add it
  to the application Compose project or replace it with another proxy.
- Only Caddy publishes public application ports. Production PostgreSQL, Django, and
  Next.js containers must not publish ports 5432, 8000, or 3000.
- Caddy reaches `frontend` and `backend` over the external `evolve_proxy` Docker network.
  PostgreSQL is isolated with Django on the internal `evolve_database` network.
- Preserve the Caddy data/config volumes and the PostgreSQL volume. Never delete persistent
  volumes or run destructive database commands without explicit authorization.
- Do not install application runtimes directly on Ubuntu when Docker can provide them.
- Back up, format, and validate the host-side Caddyfile before reload. Do not edit the
  read-only copy mounted inside the container.

## Identity and organization invariants

- `users.User` is the permanent Django user model; email is the unique login identifier.
- Organizations are the application ownership and authorization boundary.
- Normal users require an active membership and permission for organization operations.
- Django superusers are platform-wide and may cross organization boundaries; `is_staff` is
  never equivalent to organization access.
- Authorization belongs in centralized Django permissions/selectors, not frontend routes or
  scattered role-name comparisons.
- A membership has one role for now. Invitations expire seven days after server issuance and
  only token digests may be stored.
- `artists.Artist` is an organization-owned business entity separate from `users.User`; portal access uses explicit links plus active membership authorization.
- Django `/admin/` is the internal platform administration system. Next.js portal routes are
  presentation shells and must never be treated as authorization boundaries.
- Browser authentication uses same-origin Django sessions and CSRF protection. Never store
  authentication tokens in localStorage or introduce a second authentication authority.
- Frontend organization selection is transient UX state only. Every backend operation must
  authorize the supplied organization independently.
- Important organization, membership, invitation, profile, branding, domain, API credential, and platform mutations write
  immutable audit events without secrets or invitation tokens.
- Deactivate memberships, organizations, and users instead of hard-deleting operational
  identity records. Never remove the last active organization owner.

## Artist-domain invariants

- Artist UUIDs are organization owned; slugs are unique only within an organization.
- Artist team responsibility is descriptive and never replaces organization authorization roles.
- Artist portal links never grant access by themselves; active linked users still require backend-authorized active membership.
- Artist, assignment, and portal-link mutation paths must be organization scoped, audited, and deactivation based.
- Artist asset references use validated URLs; do not add arbitrary CSS or local production uploads.

## White-label and integration invariants

- Branding and verified host mappings are organization scoped and never grant access.
- Theme input is constrained to validated tokens and URL references; arbitrary CSS and local production uploads are prohibited.
- The canonical integration API remains `https://evolve.nastycsa.com/api/`.
- API secrets are returned once, stored only as SHA-256 digests, explicitly scoped, and separate from browser sessions.
- Unknown or unverified hosts must never resolve an organization. Domain verification and Caddy activation are controlled operations.
- Raw API secrets, domain-independent credentials, and private key material must never enter logs or audit metadata.

## Relationship-domain invariants

- `contacts.Contact` is an organization-owned business record, never an authentication identity or automatic link to `users.User`.
- Promoter and Venue UUIDs are canonical; their slugs are unique only inside an organization.
- PromoterContact and VenueContact must link records in the same organization. Active relationships require an active Contact.
- Relationship responsibilities are descriptive and never confer organization permissions.
- Promoter, Venue, Contact, and relationship mutations are backend-authorized, audited, and deactivation based.
- Master records remain current. Booking snapshots preserve selected historical operational values without moving Booking schema into these domains.

## Booking-domain invariants

- Bookings use globally unique UUID-backed `EV-` references and always belong to one organization and artist.
- Promoter, venue, contact, and membership links must belong to the booking organization. Booking assignments never confer authorization.
- Status changes use the explicit transition service and append-only history; generic updates must not bypass the transition graph.
- Promoter, venue, location, and assigned-contact snapshots are frozen historical values. Master-record edits never silently rewrite them.
- Commercial terms require explicit `booking.commercial.view/manage` permissions and are excluded from generic lists and developer responses.
- Important booking, status, team, and contact mutations are audited without commercial values or private credentials.

## Call Sheet invariants

- Each Booking has at most one CallSheet identity; revisions are sequential CallSheetVersion records.
- Publishing is atomic, supersedes the previous published version, and permits only one current published version.
- Published, superseded, and cancelled versions and their structured children are immutable. Changes require a new draft.
- Booking, venue, team, and contact source changes never rewrite historical versions. Refresh from Booking is explicit and draft-only.
- Call Sheets contain operational data only. Booking commercial terms, payment data, passport data, and card data are prohibited.
- Developer Call Sheet responses include only current published summaries and exclude private contact details and internal notes.

## Music-domain invariants

- Release and Track records are organization owned and primarily linked to Artist; all related placements, credits, and links must preserve organization compatibility.
- Release status changes use the centralized lifecycle service and row locking; generic updates and Django admin must not bypass it.
- ISRC and UPC/EAN values are normalized/validated and unique when non-empty. Evolve never acts as an issuing agency.
- Artist portal Music access is read-only and limited to explicitly authorized linked Artists. Internal notes remain private.
- Credits are descriptive only. Do not add royalties, payments, DSP integrations, audio storage, Campaigns, or Rollouts without a later milestone.

## Campaign and Rollout invariants

- Campaign is strategic and Rollout is operational; do not collapse them into one model.
- Campaign Artist, optional Release, ownership Membership, Rollout, milestone, task, and dependency relationships must preserve organization scope.
- Campaign, Rollout, and Task lifecycle changes use explicit services; task completion records actor/time and reopening is explicit.
- Task dependencies remain within one Rollout and reject self-links, duplicates, and cycles. Progress and overdue state are derived.
- Calendar and notification delivery remain deferred read/consumer concerns. Do not add analytics, budgets, integrations, Redis, or Celery.

## Calendar and document invariants

- Calendar source records remain authoritative; never persist duplicate projections. Standalone events alone use `CalendarEvent`.
- Calendar queries are organization scoped, permission filtered, timezone aware, and limited to 366 days. Private events and internal/commercial fields never leak.
- Documents are metadata with explicit version lineage and constrained same-organization typed links. Never introduce unrestricted generic relations.
- Binary uploads and sensitive identity documents remain disabled until durable private storage and security controls are explicitly selected. Restricted access is backend enforced.

## Notification invariants

- Notification content is immutable and separate from AuditEvent; per-user read/archive state belongs to NotificationRecipient.
- Recipient resolution requires active users and active organization memberships. Notifications never grant authorization.
- Action URLs are server-generated internal paths; content must exclude secrets, commercial amounts, restricted URLs, and sensitive data.
- In-app delivery is synchronous inside domain transactions. No Redis, Celery, WebSockets, scheduler, email, SMS, or push delivery exists.

## Finance invariants

- Booking owns commercial terms; Finance owns immutable invoice snapshots, payments, allocations, balances, and derived payment state.
- All money uses Decimal and explicit uppercase currency. Never convert or aggregate unlike currencies.
- Invoice lifecycle and payment allocation use Finance services. Issued invoices are immutable; allocated records cannot be casually voided or deleted.
- Allocation locks Payment before Invoice and must reject cross-organization, cross-currency, void, and over-allocation attempts.
- Finance data requires explicit backend permissions. Managers, members, artists, and staff-only users receive no Finance access by default.
- Store no card or bank credentials. Audit and notification content must not leak financial amounts, billing addresses, payer details, or private notes.

## Rights and royalties invariants

- Credit is not ownership; ownership is not earnings; earnings are not payment. MusicCredit,
  Rights ownership, RoyaltyAllocation, and Finance records remain separate.
- Rights percentages use Decimal 0..100 semantics. Parent Track/Work locks serialize applicable
  split validation, and overlapping territory/effective periods must never exceed 100%.
- Finalized Royalty Statements, lines, and allocations are immutable historical snapshots.
  Allocation generation is explicit and never follows later Rights changes automatically.
- RoyaltyAllocation is attributable earnings only. Payouts, bank details, taxes, and payment
  instructions require an explicit later milestone.
- Artist users see only their explicitly linked RightsParty earnings. Audits, notifications, and
  API keys must not leak royalty amounts.

## Consolidated product experience

- Global Search, dashboards, command navigation, and Artist 360 are read-only consolidation surfaces; do not duplicate domain mutation logic in them.
- Search results must be capped, curated, organization-scoped, and permission-filtered by Django. Never search private notes, secrets, audit descriptions, payment data, or royalty earnings.
- Browser-stored navigation preferences are presentation only and must never influence authorization.
- Dashboard monetary summaries must remain grouped by currency; never combine currencies.
