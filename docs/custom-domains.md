# Custom domains

`OrganizationDomain` stores a normalized globally unique hostname, secure DNS challenge,
verification status, activation and primary flags, and timestamps. Unsafe hostnames are rejected,
and the database prevents more than one active primary domain per organization.

Lifecycle:

1. An authorized organization administrator submits a hostname at `/workspace/domains`.
2. Evolve generates a TXT challenge at `_evolve-verification.<hostname>`.
3. The administrator publishes the record.
4. A platform superuser manually approves verification and activates the mapping at
   `/platform/domains`.
5. An operator adds the approved hostname to the independently managed Caddy configuration.
6. Caddy obtains and renews TLS; only then is the hostname served.

Automated DNS lookup and Caddy modification are deferred. The verification action is therefore a
manual platform approval, not evidence of an application-performed DNS query. Host resolution
accepts only exact verified, active, primary database records. It selects presentation context
only; every request still requires normal membership and permission authorization. Unknown hosts
never select an organization. `evolve.nastycsa.com` remains canonical.
