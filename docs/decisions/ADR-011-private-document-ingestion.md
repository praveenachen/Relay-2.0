# ADR-011-private-document-ingestion

Status: Accepted for Phase 4

# Context

LEARN needs real lecture inputs before the product can test reviewable study-note generation. The ingestion path must support common classroom file formats without giving uploaded content broader authority inside Relay.

# Decision

Store one original source document per LEARN run in a private local file store. Persist only metadata, checksum, storage key, status, and parsed representation in the database. Support PDF, DOCX, Markdown, and plain text through parser implementations behind a `DocumentParser` interface.

# Rationale

Keeping bytes outside JSON payloads avoids large database rows and keeps storage concerns explicit. A single source per run keeps lifecycle and duplicate handling simple for the first slice. Parser implementations produce the same `ParsedDocument` shape, so LEARN orchestration does not branch on file type after validation.

# Consequences

The local store needs operational retention and backup policy before production. PDFs without extractable text fail because OCR is out of scope. DOCX tables and embedded media are not interpreted yet.
