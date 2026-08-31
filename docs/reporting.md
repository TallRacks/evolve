# Reporting

Reporting is a read-only Django projection over authoritative domain models. Every report requires
`reporting.view` and the source-domain view permission; querysets are authorized and organization
scoped before filtering or aggregation. Reports never create warehouse copies or employee rankings.

Saved views are private to one user, organization, and report. Their filters use an explicit key
allowlist, and one view may be the default per user/organization/report. CSV exports rerun the
authorized backend query, omit hidden fields, prefix spreadsheet formula characters, and record a
privacy-safe `report.exported` audit event containing only the report key, row count, and filter keys.

Finance and royalty reporting retains Decimal values and groups each currency independently. No
currency conversion or cross-currency total is produced. Interactive report responses are paginated to 100 rows per page at most, while summaries and CSV exports are regenerated from the full authorized filtered dataset. Filters, date ranges, page values, and sort fields are allowlisted and validated by Django.
