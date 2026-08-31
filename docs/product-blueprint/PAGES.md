# Evolve Pages

The App Router currently contains 151 `page.tsx` files.

## Route families

- `/dashboard`: authorized landing and operational overview.
- `/workspace/*`: organization-scoped operational workspace.
- `/platform/*`: explicit platform-superuser views.
- `/artist/*`: curated linked-artist experience.
- `/developer/*`: API client documentation and key management.
- `/profile/*`: account, notification preferences, and security.
- `/admin/*`: Django Unfold internal administration.
- `/invite/[token]`: controlled invitation acceptance.
- `/offline`: public static failure state with no operational data.

Existing route URLs remain stable. List/detail/create/edit/print pages are retained where present. Permission-aware navigation may hide destinations, but the backend remains authoritative.

A page is considered ready only when its actual workflow includes valid data, authorization, loading/error/empty behavior, meaningful actions, and usable responsive presentation. Route existence alone does not establish readiness.
