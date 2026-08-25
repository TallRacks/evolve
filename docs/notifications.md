# Notifications

`Notification` stores immutable shared operational content; `NotificationRecipient` stores each user read/archive state. Audit events remain separate immutable evidence.

Categories are team, bookings, call sheets, music, marketing, documents, finance, and system. Priorities are low, normal, high, and urgent. Preferences are per-user category switches for in-app delivery only.

Recipient resolution is centralized and accepts only active users with active organization memberships. Actors are suppressed, recipient uniqueness is database enforced, and notifications never grant linked-resource authorization. Action URLs are server-generated internal relative paths.

Booking status, Call Sheet publishing, Release scheduling/release, and Rollout task assignment/completion create synchronous notifications inside existing atomic service transactions. Failed outer transactions therefore roll back notification rows. No scheduler exists, so upcoming/overdue notifications are deferred.

APIs provide a paginated personal inbox, unread count, read/unread, read-all, archive, and preferences. Platform oversight exposes aggregate metadata only. Organization API keys receive no notification endpoint because inbox content is personal.

Finance emits sparse `invoice.issued`, `payment.recorded`, and `invoice.paid` events. Messages use
record references and exclude amounts, billing addresses, payer details, notes, and credentials.

Rights emits a sparse royalty.statement_finalized event containing only the statement reference.
It excludes earnings, percentages, parties, documents, and internal notes.

Messages exclude commercial amounts, secrets, raw invitation tokens, restricted URLs, and sensitive personal data. Email, SMS, push, WhatsApp, WebSockets, Redis, Celery, scheduled delivery, retention automation, and digests are deferred.

## Travel integration

See `docs/travel.md` for the implemented Travel integration and its authorization, privacy, and snapshot rules.

## Production notifications

Production lifecycle and assignment services may create sparse in-app notifications for relevant active Booking team members or the assigned member. Content uses safe identifiers and excludes notes, security detail, Contact details, and other private operational data.
