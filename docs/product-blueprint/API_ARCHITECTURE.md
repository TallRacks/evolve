# Evolve API Architecture

The frontend uses same-origin `/api/` requests. Caddy routes `/api/*`, `/admin/*`, and `/static/*` to Django and application traffic to Next.js. The browser never connects to PostgreSQL.

The backend exposes 23 domain API URL modules and approximately 285 URL patterns. APIs are grouped into organization workspace, platform-superuser, artist portal, and scoped developer surfaces.

## Authentication

Browser authentication uses Django sessions and CSRF. Login and logout require valid CSRF. No JWT, Auth.js, or browser authentication token store is used.

## Authorization

Django permissions and organization-scoped selectors authorize each request. Frontend guards and navigation are UX only. `is_staff` alone grants no organization or platform bypass; active superusers have explicit platform behavior.

## Response policy

Serializers are explicit and surface-specific. Sensitive commercial, legal, contact, storage, credential, and royalty fields are omitted from broad, artist, search, notification, audit, and developer responses as defined by each domain.
