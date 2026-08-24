# Venues

`venues.Venue` is an organization-owned reusable master record with a UUID canonical identifier and organization-scoped slug. Its minimal operational profile includes location, optional coordinates, public contact information, capacity, and timezone. Coordinates must be supplied as a pair and are range validated; capacity cannot be negative.

Venues use `active`, `inactive`, and `archived` lifecycle states. Destructive application and Django-admin deletion is disabled. Production specifications, riders, stage dimensions, parking, and accommodation data are deferred.

`VenueContact` links a reusable Contact with a constrained venue responsibility, primary flag, and active state. Cross-organization and inactive-contact links are rejected by model validation shared by API and admin. One active primary contact is allowed per responsibility.

Centralized `venue.view` and `venue.manage` permissions enforce organization isolation. Platform superusers retain explicit cross-organization access; `is_staff` alone does not. Venue and relationship mutations emit `venue.*` audit events without private contact details.

`GET /api/developer/venues/` requires `venue.read` and returns a curated organization-scoped representation. Future Bookings may snapshot selected venue and operational fields for historical accuracy; no Booking or production records exist yet.
