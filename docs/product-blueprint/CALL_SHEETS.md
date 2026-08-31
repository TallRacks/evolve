# Call Sheets

The existing Call Sheet workflow remains authoritative: one identity per Booking, sequential versions, editable draft/ready states, explicit source refresh, review, publish/supersede, print styling, and immutable published history.

The Booking action queue flags missing Call Sheets and links to the existing generation workflow. Booking detail retains the visible Generate/Open action. No server PDF dependency or private offline cache was introduced.

Section reordering remains deferred because the current model has no section-order persistence and adding it was not necessary for the connectivity and command-centre work.
