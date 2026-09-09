# LEARN workflow

LEARN turns lecture files into reviewed Notion study pages.

Implemented:

- PDF, DOCX, Markdown, and text ingestion
- private local source storage
- structured parsing
- typed lecture summarization
- student review and edits
- exact-payload approval
- real Notion publishing when configured
- mock Notion publishing for local isolation and tests
- external artifact persistence

Publishing can wait until after notes are generated. A student may upload, parse, summarize, and edit without a Notion connection. Approval for real publishing requires a connected Notion workspace and selected default destination.

PLAN and COLLABORATE are not implemented beyond draft workflows.
