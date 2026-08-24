# Promoters

`promoters.Promoter` is an organization-owned reusable master record, identified by UUID with a slug unique inside its organization. It stores current identity, public business contact, location, notes, and an `active`, `inactive`, or `archived` lifecycle state. Application and admin workflows do not delete promoters.

`PromoterContact` links a reusable `contacts.Contact` to a promoter with a constrained responsibility, primary flag, and active state. Both records must belong to the same organization. A removed relationship may be safely reactivated; one active primary contact is allowed per responsibility.

Owners and administrators manage promoters. Managers view and manage them; members have read access; artist-role memberships have no promoter administration permission. Platform superusers have explicit cross-organization access. IDs and organization parameters never grant access without backend authorization.

Mutations emit `promoter.*` audit events. The read-only developer endpoint is `GET /api/developer/promoters/` and requires an organization-scoped key with `promoter.read`; private notes and linked contact details are omitted.

Promoters are master records. A future Booking may capture immutable operational/contact snapshots so historical bookings do not change when this master record changes. Booking fields and snapshots are intentionally deferred.
