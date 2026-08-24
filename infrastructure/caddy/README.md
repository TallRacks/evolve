# Caddy integration

Caddy is independently managed from `/opt/evolve`, not by the application Compose project.
The live host file is `/opt/evolve/infrastructure/caddy/Caddyfile`; the repository's
`Caddyfile.example` documents its expected routing.

Caddy joins `evolve_proxy` and resolves the stable aliases `frontend` and `backend`. It routes
`/api/*`, `/admin/*`, and `/static/*` to Django and all other canonical requests to Next.js.
The temporary hostname permanently redirects to `https://evolve.nastycsa.com{uri}`.

Always back up and format the host file, validate it inside `evolve-caddy`, then reload. Never
modify certificate storage or overwrite the read-only `/etc/caddy/Caddyfile` mount inside the
running container.
