# Royalties

Royalty Statements are historical earnings-attribution records, separate from operational
Finance. An Invoice or Payment never becomes a royalty statement, and a RoyaltyAllocation never
represents money paid.

RoyaltyStatement uses UUID identity, a server-generated ROY-YYYY-random reference, source, period,
one uppercase currency, optional declared total, optional same-organization source Document, and
draft/finalized/void lifecycle. Calculated total derives from line net amounts; variance is
declared minus calculated. No currency conversion exists.

Lines capture optional Track, Release, and Artist references, external reference, territory,
platform, usage, Decimal quantity, gross, deductions, derived net, and an explicit Master,
Publishing, Mixed, or Other basis. Evolve never guesses the earnings basis.

Automatic generation is explicit and row locked, using rights applicable at the statement period
end. It requires a resolved Track and Master or Publishing basis. Mixed and Other use manual
allocation. Generation never follows later Rights changes and cannot duplicate allocations.

Allocations cannot exceed 100 percent or line net amount. Incomplete drafts are allowed.
Finalization locks statement and lines, requires full allocation, freezes history, audits the
transition, and emits an amount-free notification. Corrections use void plus replacement.

Audit and notification descriptions omit earnings, percentages, party details, and notes. API
keys receive no royalty endpoint. Artist portal responses contain only finalized amounts
attributed to that artist-linked RightsParty.

Payouts, bank details, taxes, ingestion, CSV mapping, DDEX, societies, registrations, exchange
rates, forecasting, contracts, settlements, and ledger accounting remain deferred.
