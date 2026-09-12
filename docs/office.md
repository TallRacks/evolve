# Evolve Office (29B)

Evolve-native Office content is stored as validated structured JSON in
`OfficeDocumentContent`. The existing `Document` remains the metadata,
visibility, typed-link, and storage boundary. `DocumentRevision` records
immutable numbered checkpoints; a save supplies the expected revision and
returns a conflict instead of overwriting a newer save. Restore is implemented
as a new revision.

The current editor is a deliberately small structured block editor. It does
not execute HTML, scripts, arbitrary links, formulas, or embeds. It provides
document, note, checklist, and sheet format entry points while richer toolbar
semantics and a mature Tiptap/Lexical editor evaluation remain follow-up work.
There is no realtime cursor/CRDT collaboration and no offline private-content
cache.

Google remains optional. Existing Google Workspace configuration continues to
show its honest provider state; native Evolve editing does not depend on it.
Google copy/import/snapshot flows are deferred until the provider OAuth and
capability model is implemented and tested.
