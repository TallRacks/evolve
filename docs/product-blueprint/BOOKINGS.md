# Booking Operations

Bookings use the existing lifecycle, creation automation, routes, and organization authorization.

## Directory

The directory combines an action queue for the next 30 days with collapsible month groups. Priority uses the stored Urgent, High, Normal, and Low values and displays P1 through P4 without changing the model enum. Days Out is derived from the server's current date and is never stored.

Django returns Production, Travel, and Call Sheet readiness. Contract and Invoice readiness are included only when the caller independently has `contract.view` and `finance.view`. Each readiness state links to the existing record or existing create/open workflow.

## Detail

Booking detail retains Edit, status transition, team/contact assignment, automated operational setup, Call Sheet generation, Contracts, Production, Travel, Finance, Documents, history, and Activity. A compact readiness strip provides direct operational navigation.
