# White-label foundation

Branding is organization scoped through `OrganizationBranding`. It supports a display name,
logo and favicon URL references, support details, and validated six-digit hex tokens for primary,
secondary, accent, background, surface, primary text, and muted text. Arbitrary CSS, HTML, local
production uploads, and object storage were intentionally not introduced.

`GET /api/branding/current/?organization_id=<uuid>` returns effective tokens only after Django
authorizes the user for that organization. `GET/PATCH /api/organizations/<uuid>/branding/`
reads or updates configuration; updates require `branding.manage` and emit `branding.updated`.
Platform superusers may inspect and update any organization through `/api/platform/branding/`.

The Next.js shell applies identity and selected restrained tokens while retaining fixed semantic
success, warning, error, and destructive colors. Missing or loading branding uses Evolve defaults.
The workspace editor is `/workspace/branding`; platform views are `/platform/branding` and its
organization detail routes. Logo and favicon storage remain URL-reference based until a managed
asset-storage design is approved.
