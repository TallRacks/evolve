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
- Artist remains a future domain entity separate from User.
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

## White-label and integration invariants

- Branding and verified host mappings are organization scoped and never grant access.
- Theme input is constrained to validated tokens and URL references; arbitrary CSS and local production uploads are prohibited.
- The canonical integration API remains `https://evolve.nastycsa.com/api/`.
- API secrets are returned once, stored only as SHA-256 digests, explicitly scoped, and separate from browser sessions.
- Unknown or unverified hosts must never resolve an organization. Domain verification and Caddy activation are controlled operations.
- Raw API secrets, domain-independent credentials, and private key material must never enter logs or audit metadata.
