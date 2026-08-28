# Contracts and agreements

## Boundary

The `contracts` Django app owns agreement identity, lifecycle, historical party snapshots,
structured terms and plain-text sections, internal approvals, manual signing status, and typed
Document links. Artist, Booking, Promoter, Contact, RightsParty, Invoice, Payment, Document,
Membership, User, and Organization remain references owned by their existing domains.

A Contract is not a Document binary, Booking commercial record, Finance ledger, or Rights
ownership instruction. Contractual value does not create an Invoice; legal language does not
mutate Rights. Credit, ownership, earnings, and payment remain separate.

## Lifecycle and integrity

Stored workflow states are Draft, In review, Approved, Sent, Partially signed, Executed,
Terminated, Cancelled, and Archived. Expiry is derived for executed Contracts whose expiry date
has passed; no scheduler is implied. All changes use transactional services and the allowed
transition graph. Generic PATCH cannot set status.

Execution requires at least one party and term, no pending or rejected approval request, and all
required signatories manually marked Signed. Signing status is operational metadata only. Evolve
does not verify identity, create cryptographic signatures, store signature images, or claim legal
electronic execution.

Executed Contract identity, relationships, dates, legal fields, summaries, parties, terms, and
sections are immutable. Termination requires a reason and is audited. Corrections should use a
future amendment or replacement workflow rather than rewriting history.

## Parties and snapshots

A party may link one Artist, Promoter, Contact, or RightsParty, or remain an external legal
entity. Links must remain inside the Contract organization. Display name and optional legal name,
email, and address are snapshots; later master-record changes do not rewrite them. Party roles
describe the agreement and never grant application authorization.

## Terms, sections, and approvals

Terms support explicit text, Decimal, currency, date, or boolean values without becoming a legal
rules engine or Finance ledger. Sections are ordered plain text, never arbitrary HTML. Draft and
In-review content is editable; later workflow states reject content mutation.

Approval requests target active same-organization memberships whose user has
`contract.approve`. Only the assigned user, or an explicit platform superuser, may decide the
request. Approval is internal workflow and is distinct from signature status.

## Authorization and privacy

Workspace access uses `contract.view`, `contract.manage`, `contract.approve`,
`contract.status.manage`, `contract.sensitive.view`, and `contract.signature.manage`. Owners and
administrators receive the full set; managers receive view/manage/status/signature operations;
members receive no Contract access by default. `is_staff` never bypasses access. Platform Django
superusers retain explicit cross-organization access.

Artist-linked users use `/api/artist/contracts/`, which returns only executed Contracts linked to
their authorized Artist and excludes parties, terms, sections, approvals, internal notes,
Documents, signing details, and values. Workspace detail serializers are available only to roles
with explicit Contract access.

## Integrations

Booking detail can explicitly create a Draft Contract. It snapshots context and may copy a Draft
performance-fee term only when the actor can already view Booking commercial data. It never
creates an Invoice. Artist 360 and Promoter relationships show safe Contract summaries.

Contract Document links use same-organization external-reference Document metadata. Existing
binary-upload restrictions remain unchanged. Notifications contain a reference and action only;
audit descriptions contain actions and changed field names rather than legal text, addresses,
comments, signing notes, or values. Contract expiry is a computed Calendar projection for users
with `contract.view`; no reminder scheduler exists.

Global Search indexes reference, title, Artist, Booking reference, and Promoter only. Dashboard
counts use real in-review, assigned-pending-approval, and unsigned records. The `contract.read`
developer scope exposes only identity, relationship summaries, workflow status, and dates.

## Routes

Workspace routes are `/workspace/contracts`, `/workspace/contracts/new`,
`/workspace/contracts/{id}`, `/workspace/contracts/{id}/edit`, and the HTML print summary at
`/workspace/contracts/{id}/print`. Platform list/detail routes require a superuser. Django Unfold
provides protected operational administration under Content & Documents.

Electronic signatures, PDF generation, binary upload, redlining, amendment/version engines,
legal analysis, automated Rights mutation, and automatic Invoice generation remain deferred.
