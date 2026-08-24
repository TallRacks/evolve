# Contacts

`contacts.Contact` is a reusable organization-owned real-world business contact. It is not `users.User`, does not provide authentication, and is never linked to an Evolve login automatically. A contact may be linked to promoters, venues, and future operational records.

The record contains name, optional title, email, phone/mobile, notes, and a single active flag. Deactivation is preferred over deletion. Contact notes remain internal session-authenticated data and are not exposed through the developer API.

Promoter and venue relationship models retain their own responsibility, primary, and active state. Domain validation rejects cross-organization relationships and new links to inactive contacts. Relationship removal does not delete the Contact.

Centralized `contact.view` and `contact.manage` permissions enforce organization scoping. Owners/admins and managers manage contacts; members may view them; artist-role memberships receive no contact directory access. Contact mutations produce privacy-conscious audit descriptions without names, email addresses, phone numbers, or notes.

Future Booking workflows will select these master contacts and may store immutable snapshots of selected operational details. That snapshot behavior is deferred with the Booking domain.
