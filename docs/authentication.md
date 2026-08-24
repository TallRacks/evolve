# Authentication

Django is the source of truth for identity and authentication. The initial API enables
Django session authentication, which fits the same-origin Caddy architecture and Django
admin. The public health endpoint is the only anonymous API behavior currently defined.

The frontend must not persist database credentials or bypass Django. Detailed login,
session lifetime, account recovery, multi-factor authentication, and invitation flows
require product decisions before implementation.

Production cookies are secure and CSRF protection remains enabled. Trusted origins and
allowed hosts are configured through environment variables.
