# Calendar

The unified calendar is a bounded read projection. Booking, published Call Sheet, Release, Campaign, Rollout Milestone, and Rollout Task dates remain in their source tables; only standalone operational events use `CalendarEvent`.

## Access and visibility

- `calendar.view` reads organization projections; `calendar.manage` mutates standalone events.
- Organization events are visible to authorized members. Artist-team events require an Artist and are visible in the linked Artist portal. Private events are limited to creator, owner, and platform superusers.
- Artist portal output excludes internal Rollout work and unrelated/private events. Booking projections never include commercial fields.
- Platform superusers may query one organization at a time. Staff status alone grants nothing.

## Time and performance

The API requires ISO-8601 `start` and `end`, rejects inverted or greater-than-366-day windows, returns aware ISO-8601 values, and uses source timezone semantics where available. The browser displays values in its current locale/timezone. Queries are organization/date scoped and relation-loaded; no Redis cache exists.

## APIs

- `GET /api/calendar/`
- `GET|POST /api/calendar/events/` and `GET|PATCH /api/calendar/events/{id}/`
- `POST /api/calendar/events/{id}/status/`
- `GET /api/artist-portal/calendar/`, `/api/platform/calendar/`, and `/api/developer/calendar/` (`calendar.read`)

External calendar sync, recurring events, notifications, and travel projections are deferred.

## Travel integration

See `docs/travel.md` for the implemented Travel integration and its authorization, privacy, and snapshot rules.

## Production projection

Calendar projects Production advance due times and active non-cancelled schedule items for authorized users. Production `show` items are omitted because Booking already projects the show event. Artist projection remains limited to linked Artists and safe fields.
