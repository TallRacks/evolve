# Travel and itinerary operations

Travel is an organization-owned domain centered on `TravelItinerary`. An itinerary belongs to one Artist and may link one Booking for that same Artist and organization. It contains travellers, ordered transport segments, accommodation stays, segment assignments, and room assignments. Cross-organization and cross-itinerary relationships are rejected by Django model and service validation.

## Travellers and privacy

Travellers may reference an Artist, an access-valid organization Membership, or an external display name. Artist, team, guest, crew, and other types are supported. Email and phone snapshots are optional operational contact details. Artist portal responses omit traveller contact details, internal notes, confirmation references, driver phones, and unrelated travellers.

Evolve does not store passport or national-ID numbers, identity/visa scans, payment cards, bank information, airline or loyalty credentials, boarding passes, or immigration records. There is no identity-document vault. Any future identity-document storage requires a separate security architecture milestone.

## Transport and accommodation

A `TravelSegment` represents flight, rail, ground, ferry, or other transport. Common scheduling and routing fields are shared; flights add airline, flight number, and validated three-letter airport codes, while ground transport can capture a driver and operational phone. No airline, hotel, tracking, mapping, or booking API is integrated.

Accommodation stays hold property, location, local timezone, check-in/out, operational contact, and optional confirmation reference. Room assignments link only travellers from the same itinerary. Confirmation references remain workspace-private and are excluded from search, notifications, Artist responses, and developer responses.

## Timezones and lifecycle

All event timestamps are timezone-aware UTC instants. Each itinerary, segment endpoint, and accommodation stay retains an IANA timezone identifier so the frontend can display local wall time. Durations are derived from timestamps.

Itinerary transitions are `draft -> confirmed/cancelled`, `confirmed -> in_progress/cancelled`, `in_progress -> completed/cancelled`, and `completed/cancelled -> archived`. Segment and accommodation transitions are similarly explicit. Generic updates cannot change status; lifecycle services lock the direct record and audit the transition.

## Integrations

- Booking detail provides an explicit create/open itinerary workflow. Travel data is not duplicated on Booking.
- A draft or ready Call Sheet version can explicitly replace its travel/accommodation rows from the linked itinerary. Published, superseded, and cancelled snapshots remain immutable.
- Calendar projects segment departures and accommodation check-ins without persisting duplicate events. Workspace projection requires `travel.view`; Artist projection is limited to linked Artists.
- Documents may link explicitly to an itinerary, segment, or accommodation stay. Existing HTTPS external-reference and visibility rules remain authoritative; binary and identity-document uploads remain disabled.
- Confirmation sends a sparse in-app notification only to active membership-backed travellers. Notification text excludes references and contact details.
- Global Search returns permission-filtered itinerary records but never searches confirmation references or traveller contacts.
- `GET /api/developer/travel/itineraries/` requires `travel.read` and returns a conservative organization-scoped schedule without contacts, references, notes, or private document URLs.

Workspace management requires centralized `travel.view`, `travel.manage`, and `travel.status.manage` permissions. Owners and admins have full Travel access, managers can manage Travel, members can read it, Artist users use only the curated read-only portal, platform access requires superuser, and `is_staff` grants no bypass.

## Production relationship

Travel remains a parallel Booking-owned operational input. Production detail projects the linked itinerary and opens or creates Travel without copying transport, accommodation, confirmation, or private contact data into Production. Call Sheet Travel and Production imports remain separate explicit snapshot actions.
