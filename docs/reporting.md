# Reporting

Reporting is a read-only Django projection over authoritative domain models. Every report requires
`reporting.view` and the source-domain view permission; querysets are authorized and organization
scoped before filtering or aggregation. Reports never create warehouse copies or employee rankings.

Saved views are private to one user, organization, and report. Their filters use an explicit key
allowlist, and one view may be the default per user/organization/report. CSV exports rerun the
authorized backend query, omit hidden fields, prefix spreadsheet formula characters, and record a
privacy-safe `report.exported` audit event containing only the report key, row count, and filter keys.

Finance and royalty reporting retains Decimal values and groups each currency independently. No
currency conversion or cross-currency total is produced. Report row limits prevent unbounded
responses; larger export/pagination infrastructure can be introduced when measured demand requires it.
