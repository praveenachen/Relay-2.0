# Document processing

Relay accepts one source document per LEARN run. The original bytes are stored in the local private file store and referenced by an opaque storage key. API responses expose the user-facing filename, content type, size, checksum, parser metadata, and section identities, but never the storage path.

## Supported inputs

| Format | Parser | Notes |
| --- | --- | --- |
| PDF | PyMuPDF | Extracts page text. OCR is not performed. Blank/image-only PDFs fail safely. |
| DOCX | python-docx | Extracts paragraphs and heading styles. Tables and embedded images are not interpreted. |
| Markdown | Internal parser | Preserves ATX heading boundaries and avoids treating fenced code headings as sections. |
| Plain text | Internal parser | Decodes UTF-8, normalizes newlines, and rejects binary-looking content. |

Validation checks extension, content type, upload size, basic file signature for PDF/DOCX, empty content, binary markers in text, and a maximum parsed character budget. Parser failures map to safe HTTP errors without logging or returning source content.

## Parsed representation

The canonical parsed form is `ParsedDocument`:

- `title`: optional title inferred by the parser.
- `metadata`: filename, page count when known, character count, and parser name.
- `sections`: ordered `DocumentSection` records with stable section ids, heading/level, text, and optional page ranges.

Summary generation uses the full parsed sections internally. Public detail responses omit section `text` to avoid turning run detail into a source-document echo endpoint.

## Segmentation policy

Segmentation is conservative and structure-first:

1. Keep sections intact when they fit the configured budget.
2. Split oversized sections on blank-line paragraph boundaries.
3. Split oversized paragraphs on whitespace.
4. Split oversized tokens by character as the final fallback.

The budget is measured as UTF-8 bytes through `estimated_tokens`. This is intentionally conservative and stable across providers; it is not an exact tokenizer. Segments preserve the original section id, heading, order, and page metadata so model output can keep provenance references.

Small documents are summarized in one direct call. Larger documents use bounded per-section calls and deterministic aggregation instead of sending an unbounded final prompt.
