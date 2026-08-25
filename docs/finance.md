# Finance

Finance is an organization-owned Django domain separate from Booking. Creating an invoice from a
Booking deliberately snapshots the Artist, billed party, currency, due date, and performance fee.
Later Booking edits never rewrite that invoice.

## Records and lifecycle

Invoice uses a UUID plus a unique server-generated `INV-YYYY-<random>` reference, avoiding unsafe
counter races. Draft invoices are editable. Issuing requires billing identity, line items, and a
positive total. Issued financial content is immutable; voiding is explicit, audited, and denied
while active allocations exist. Correction is currently void plus replacement; credit notes are
deferred.

Workflow state is stored as draft, issued, void, or cancelled. Payment state is derived as unpaid,
partially paid, paid, or overdue. Overdue means an issued invoice has a past due date and positive
balance, so no scheduler is needed.

InvoiceLineItem requires positive Decimal quantity and non-negative Decimal unit amount. The server
derives line totals and subtotal. Tax is a manually entered non-negative amount; Evolve provides no
tax engine or jurisdictional-compliance claim.

Payment uses a UUID plus unique `PAY-YYYY-<random>` reference, positive Decimal amount, currency,
date, descriptive method/reference, and recorded/void lifecycle. It stores no card, bank-account,
CVV, login, or gateway credentials. PaymentAllocation links a payment to an issued invoice.

## Currency and locking

Currency is an uppercase three-letter code. Evolve performs no conversion and overview totals are
grouped by currency. Allocation locks Payment first and Invoice second, then recalculates payment
remaining and invoice balance. PostgreSQL concurrency tests cover simultaneous allocations.

## Permissions and privacy

The permissions are `finance.view`, `finance.manage`, `finance.invoice.issue`,
`finance.payment.record`, and `finance.payment.allocate`. Owners and administrators receive them;
managers, members, and artists do not. Superusers have platform access; `is_staff` alone grants
nothing. Artist portal Finance is deferred.

Finance APIs enforce backend scope. Audit descriptions contain identifiers and changed field names,
not amounts, addresses, payer details, or notes. Notifications contain references but no amounts.
The explicit `finance.read` API-key scope returns curated summaries excluding billing address/email,
payer identity, notes, audit data, and allocation actors.

## Presentation and deferrals

Workspace and platform routes provide Finance workflows. Booking detail embeds a permission-gated
projection without storing totals on Booking. The authenticated print view uses constrained
organization branding. There is no PDF service, binary storage, automatic Document creation,
email, or scheduler.

FinanceSettings, credit notes, refunds, ledgers, journals, tax automation, reconciliation,
gateways, bank feeds, FX, payroll, royalties, invoice emails, and PDF infrastructure are deferred.
