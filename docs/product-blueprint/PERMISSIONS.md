# Evolve Permissions

Django is the sole authorization authority. Ordinary users require an active user, active organization, active membership, and the relevant explicit permission. Platform superusers have explicit cross-organization access. `is_staff` alone is never sufficient.

Permission families remain independent, including artist, booking, call sheet, music, campaign, calendar, document, finance, rights, royalties, travel, production, contract, task, reporting, membership, branding, domain, and API management.

Frontend rules:

- Session bootstrap returns safe identity, memberships, organizations, and permission names.
- Route guards prevent content flashes but do not secure data.
- Navigation filters by bootstrap permissions.
- Changing selected organization never expands backend access.
- Installed-PWA shortcuts and bottom navigation point only to existing routes; APIs still authorize access.

Sensitive permissions remain separate, including commercial booking access, restricted documents, contract-sensitive data, private travel contacts, Rights, Royalties, Finance, and platform configuration.
