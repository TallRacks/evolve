# Evolve Office functional checkpoint

## Editor decision

Office uses Tiptap/ProseMirror. It is React/TypeScript compatible, emits structured JSON, and provides maintained extensions for headings, marks, lists, task lists, links, tables, quotes, undo/redo, and mobile-friendly editor commands. Raw HTML is not authoritative.

## Current save contract

The Django `OfficeDocumentContent` JSON tree remains canonical and is validated server-side against the supported node allowlist. Existing optimistic concurrency remains active: writes include the expected revision and stale writes return HTTP 409. The web editor marks content Unsaved immediately and autosaves after 1.8 seconds of idle time. Saved is shown only after server confirmation. Version History previews stored JSON and Restore creates a new revision.

## Workspace context

Documents may now be assigned to a same-organization Workspace. Office list, read, create, save, and revision requests can carry `workspace_id`; archived, cross-organization, or unauthorized workspace IDs are rejected. A blank workspace selection means the organization-wide Office view.

## Intentionally remaining for the next Office slice

Typed/persisted Sheets with CSV import/export, Document-to-Task service integration, private attachments/image resolution, Booking/Music Office generators, comments/mentions in the editor, and Google interoperability are not represented as complete here. The functional-completion gate must remain FAIL until those contracts and authenticated production smoke tests exist.
