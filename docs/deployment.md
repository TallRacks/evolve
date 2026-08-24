# Deployment

## Live environment

The canonical origin is `https://evolve.nastycsa.com` on the Ubuntu 24.04 host
`evolve-prod`. The deployment checkout is `/opt/evolve/app`. The previous hostname,
`evolve-dev.escopia.com`, permanently redirects to the same path on the canonical origin.

Caddy is independently managed by `/opt/evolve/compose.yml` with its host configuration at
`/opt/evolve/infrastructure/caddy/Caddyfile`. Its `evolve_caddy_data` and
`evolve_caddy_config` volumes contain persistent ACME state and must not be removed.
Automatic HTTPS obtains and renews certificates; Certbot and manual certificates are not
used.

Production secrets are stored outside Git at `/opt/evolve/secrets/evolve.env`. The directory
has mode `700` and the file mode `600`. Do not print, copy into the repository, or replace
existing credentials during routine deployments.

## Networks and routing

`evolve_proxy` connects only Caddy, Next.js, and Django. `evolve_database` is internal and
connects only Django and PostgreSQL. Caddy routes `/api/*`, `/admin/*`, and `/static/*` to
Django without stripping their prefixes; all other paths route to Next.js. PostgreSQL,
Django, and Next.js publish no host ports.

Django uses Gunicorn in production. WhiteNoise serves collected static files from the
persistent `evolve_static_data` volume through Django and Caddy.

## Deployment procedure

From `/opt/evolve/app`:

```bash
docker network inspect evolve_proxy >/dev/null
docker compose -f compose.production.yml config --quiet
docker compose -f compose.production.yml build backend frontend
docker compose -f compose.production.yml up -d postgres
docker compose -f compose.production.yml run --rm backend python manage.py migrate --plan
docker compose -f compose.production.yml run --rm backend python manage.py migrate --noinput
docker compose -f compose.production.yml run --rm backend python manage.py collectstatic --noinput
docker compose -f compose.production.yml up -d backend frontend
docker compose -f compose.production.yml ps
```

Always inspect the migration plan before applying it. Never generate migrations or perform
destructive database operations as part of deployment.

After changing Caddy, back up the host Caddyfile, format it through a writable one-off Caddy
container, validate with `caddy validate`, and reload the existing container. Do not restart
Caddy merely to load configuration.

## Health and rollback

The backend health endpoint is `/api/health/`; the expected response is
`{"status":"ok","service":"evolve-api"}`. Both application containers define health
checks. Validate the frontend, admin login, static assets, canonical TLS, and temporary-domain
redirect after each deployment.

For application rollback, check out the previously known-good commit, rebuild its production
images, inspect its reverse migration implications, and recreate backend/frontend. Do not
reverse migrations automatically. Restore the backed-up host Caddyfile and validate/reload it
only when rolling back routing. Database and certificate volumes remain in place.

## Platform superuser password

The initial platform account is `admin@evolve.nastycsa.com`. Its generated bootstrap password
is not stored or printed. Set a known password through Django's interactive, hashed-password
workflow from `/opt/evolve/app`:

```bash
docker compose -f compose.production.yml exec backend \
  python manage.py changepassword admin@evolve.nastycsa.com
```

Enter the new password only at the protected terminal prompt. Do not place it in shell
arguments, environment templates, documentation, or Git.
