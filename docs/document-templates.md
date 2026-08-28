# Document Templates

DocumentTemplate and ordered DocumentTemplateSection records provide controlled organization templates plus platform defaults. Templates have draft, active, and inactive lifecycle states and an incrementing version. Workspace users may edit organization templates only; platform defaults require a platform superuser.

The renderer accepts only the documented simple variables for organization, artist, booking, venue, and promoter data. It rejects unknown variables, attribute traversal, filters, Django template tags/comments, arbitrary expressions, and unmatched template syntax. It performs deterministic plain-text substitution and reports missing values. React renders preview and generated content as text, not raw HTML.

Generation currently uses an authorized Booking as structured context. It creates an ordinary Document with immutable rendered content, template reference, template version, and typed Booking link. Later template changes never rewrite historical generated content. Generated documents do not imply PDF/DOCX generation, binary storage, contracts, invoices, Rights changes, or electronic signatures.
