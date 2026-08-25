# Rights management

Rights is an organization-owned Django domain for operational rights information supplied by
users. Evolve does not verify legal title, issue identifiers, register works with societies, or
guarantee legal correctness.

Credit is not ownership. Ownership is not earnings. Earnings are not payment.

- music.Track is a recording and music.MusicCredit is descriptive catalog credit.
- rights.Work is the composition. TrackWork permits many recordings of one Work and multiple
  Works for medleys or adaptations.
- RightsParty represents an artist, writer, producer, publisher, label, company, estate, or
  name-only party. It does not require a User account.
- WorkContributor is descriptive contribution and never implies ownership.
- MasterRight records Track ownership; PublishingRight records Work ownership.

No MusicCredit is migrated or interpreted as ownership automatically.

Percentages use Decimal human semantics from 0.0001 through 100.0000. Applicable ownership may
remain below 100 while incomplete, but transactional services reject totals above 100. Track or
Work parent rows are locked before validation so concurrent PostgreSQL requests cannot
over-allocate.

Territories are WORLDWIDE or conservative two-letter ISO-style codes. Worldwide overlaps every
country. Effective periods are inclusive and must have an end on or after the start. Regional
hierarchies, treaty rules, contract interpretation, and legal-rights reasoning are deferred.

ISWC values normalize to uppercase T plus ten digits. Evolve does not issue ISWC or ISRC.

rights.view and rights.manage belong to owners and administrators. Platform superusers cross
organizations; is_staff never bypasses scope. Artist users see only finalized allocations for a
RightsParty explicitly linked to their authorized Artist.

The rights.read integration scope exposes curated Work, contributor, Track, and ownership
summaries. It omits contacts, notes, contracts, audit data, and all royalty earnings.

Work and RoyaltyStatement may reference a same-organization external-reference Document. Binary
upload and sensitive-document storage remain disabled.
