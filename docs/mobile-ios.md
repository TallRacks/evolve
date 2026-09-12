# iOS and App Store preparation

The native project is prepared for Expo development and eventual TestFlight,
but no Apple account, signing certificate, provisioning profile, or App Store
submission is present.

- App name: Evolve
- Placeholder bundle identifier: `com.pending.evolve` — HUMAN DECISION REQUIRED; ownership is not confirmed
- Production API origin: `https://evolve.nastycsa.com`
- Environments: development, staging, production; local defaults never point to production
- Signing boundary: Apple Developer account and CI/TestFlight credentials stay outside Git
- Required before distribution: icons, splash review, privacy/support URLs, App Store Connect record, privacy questionnaire, account deletion policy, and Universal Links association
- Planned sequence: architecture → native foundation → approved mobile auth → internal TestFlight → external TestFlight → privacy/security review → App Store submission
- Push notifications are a future APNs/Expo capability; tokens are not credentials and sensitive lock-screen content is excluded by default

Account deletion needs policy review because organization/employment records
may require retention and deactivation rather than generic self-delete. No
automatic deletion is implemented.

## Mobile data inventory preparation

The client may handle account identity, email, organization membership, tasks,
bookings, travel, documents, notifications, AI conversations, and authorized
finance/rights data. Evolve currently has no advertising, tracking SDK,
third-party analytics SDK, or external crash-reporting SDK. These notes prepare
future App Store disclosure; they are not final legal answers.
