# Notifications

Notification is the authoritative operational event shown through recipient-specific in-app rows. Email is an optional delivery channel for a small allowlist of those events; it does not grant access, duplicate business state, or change linked-resource permissions.

Recipient resolution accepts only active users with active organization memberships. Actors are suppressed, recipient uniqueness is database enforced, and internal action URLs are server-generated relative paths. Email delivery rechecks active identity, organization access, resource permission, category preference, address validity, and connector state at send time.

The personal APIs provide a paginated inbox, unread count, read/unread, read-all, archive, and per-category in-app/email preferences. Reset restores code-defined defaults. Email failure does not alter unread state. Users may see the latest email status attached to their own inbox row; full delivery logs are platform-superuser only.

Task assignment/reassignment, Contract approval requests, and published Call Sheets may generate sparse transactional email after commit. Organization invitations use the same delivery adapter without storing the raw invitation token in a log. Other categories remain in-app by default unless an explicit event policy is added.

Notification and email content excludes commercial amounts, credentials, raw tokens, restricted documents, contract text, private notes, and sensitive personal data. SMS, WhatsApp, push delivery, WebSockets, digests, scheduled reminders, marketing mail, and bulk organization broadcasts remain deferred.
