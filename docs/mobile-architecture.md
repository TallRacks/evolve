# Native mobile architecture

Evolve is a multi-client platform: Next.js web/PWA and a genuine React Native
Expo client consume the same Django/DRF API. The native client is not a WebView,
does not contain business authorization, and does not duplicate domain models.

## Repository and client boundary

`mobile/` is an independent Expo Router project. Web components remain in
`frontend/`; native components use React Native primitives. A future `packages/`
workspace is deliberately deferred until typed API contracts can be extracted
without importing DOM, Tailwind, or browser-storage assumptions. Portable
status/permission vocabulary is documented first and can later become a small
package.

The current native API adapter has a development-only mock session switch and a
typed normalized error model. Production credentials and mobile auth endpoints
are not implemented in this phase.

## Authentication decision gate

Recommendation for review: a dedicated opaque random access/refresh credential
model, stored hashed server-side, short-lived, rotated, revocable per device,
and held in iOS Keychain/Android Keystore through SecureStore. Django remains
the authority and browser sessions remain unchanged. JWT is not recommended
merely for convention. No credential model or migration may be introduced
until the security owner approves lifecycle, revocation, 14-day reauthentication,
device logout, rotation, and breach-response details.

## Safety boundaries

The app never logs credentials, stores auth material in AsyncStorage, caches
private APIs broadly, or replays sensitive mutations offline. API permissions,
organization context, Action Gateway policy, and domain services remain server
side. Deep links validate route parameters and authorization after navigation.

Offline is currently connectivity awareness only. Selective encrypted caching
of published call sheets or today's itinerary is future work.
