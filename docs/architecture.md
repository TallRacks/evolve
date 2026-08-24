# Architecture

Evolve uses a same-origin, layered web architecture:

```text
Internet
   |
   v
Caddy
   |
   v
Next.js frontend
   |
   v
Django API
   |
   v
PostgreSQL
```

Caddy is the only public entry point and terminates TLS. Requests are routed as follows:

| Path | Destination |
| --- | --- |
| `/` | Next.js frontend |
| `/api/*` | Django API |
| `/admin/*` | Django admin |
| `/static/*` | Django static files |

The diagram expresses ownership and request flow: browser code calls the Django API
through the same public origin and never connects to PostgreSQL. Django owns data access,
authentication, authorization, validation, and business logic. Next.js owns presentation
and browser interaction.

The initial Compose stack contains PostgreSQL, Django, and Next.js. Caddy is deliberately
excluded because the VPS already runs it independently. In production, all application
services join private Docker networking and only Caddy publishes host ports 80 and 443.

No asynchronous worker, cache, message broker, or microservice is part of this foundation.
Those components require a demonstrated need and an explicit architecture decision.

## Production topology

The canonical origin is `https://evolve.nastycsa.com`. Caddy is independently managed and
joins `evolve_proxy` with the frontend and backend. Django and PostgreSQL additionally share
the internal `evolve_database` network; Caddy and the frontend cannot reach PostgreSQL.
Application containers expose ports only to Docker networks, while Caddy alone publishes
host ports 80 and 443.

## Portal and authorization boundaries

Next.js presents `/login`, `/dashboard`, `/platform`, `/workspace`, and `/artist`. These routes
separate future user experiences but confer no authority. Django sessions identify users, and
Django organization permission helpers enforce all data access. Django `/admin/` remains the
platform-superuser operations interface.

The App Router root installs a small client-side auth provider. It bootstraps from
`/api/auth/me/`, holds no credential or session token, and uses same-origin cookies for API
requests. Client route guards improve navigation but do not replace Django permissions.
Organization selection is tab-local presentation state; backend requests must reauthorize
any supplied organization identifier.
## Management portals

The authenticated Next.js shell has a persistent desktop sidebar and a mobile slide-over.
Workspace routes provide organization overview, team, invitations, and settings. Platform
routes provide superuser-only organization, user, and audit views. The profile route provides
safe self-service name editing. Django admin remains a separate Unfold operations console.

Explicit DRF API views serve only the data and mutations required by these routes. They
resolve organization identifiers through authorized querysets and record important mutations
in the read-only AuditEvent log.
