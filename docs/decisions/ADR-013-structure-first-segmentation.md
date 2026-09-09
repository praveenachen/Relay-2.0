# ADR-013-structure-first-segmentation

Status: Accepted for Phase 4

# Context

Lecture documents can exceed a single model call budget. Splitting content poorly can destroy headings, page provenance, and reviewer trust.

# Decision

Segment only when the parsed document exceeds the direct summary budget. Preserve sections when possible, then split oversized text by paragraphs, whitespace, and finally characters. Use UTF-8 byte length as a conservative provider-independent budget estimate.

# Rationale

Parsed sections carry the source identity the summary must cite. Keeping that identity across segments lets Relay validate model references after every call. UTF-8 bytes are not a tokenizer, but they are stable, fast, and conservative enough for this vertical slice.

# Consequences

Segment budgets may be less efficient than model-specific tokenizers. Very large single paragraphs can still be split in awkward places. A later provider-specific tokenizer can replace the estimator without changing the workflow contract.
