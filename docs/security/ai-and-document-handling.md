# AI and document handling

LEARN treats uploaded documents and model output as untrusted. The source can influence a generated summary, but it cannot authorize execution, select another user's run, access storage paths, or bypass approval.

## Private local files

Uploaded bytes are saved through `LocalFileStore` under the configured `DOCUMENT_STORAGE_PATH`. Keys are generated server-side and constrained to a local filename pattern. Reads and deletes resolve paths inside the configured root. Storage keys are never returned to the frontend.

The API allows the owner to download the original source for a LEARN run. It returns a generic attachment name and does not expose the on-disk path.

## Model boundary

The language-model port accepts messages and a Pydantic response model. Providers must return a typed `LectureSummary`; malformed output becomes `MALFORMED_MODEL_OUTPUT`. The summary service revalidates schema and source references after every provider call.

The OpenAI adapter uses the Responses API schema parsing interface, a configured timeout, `max_retries=0`, and `store=false`. The fake adapter is deterministic and intended for local development and tests.

## Approval and execution

Generated and edited summaries become a `create_notion_study_page` proposed action. The generic approval service still performs exact JSON matching and freezes the approved payload. Execution reads only `approved_payload`, never the mutable proposed action body.

The current connector is `MockNotionConnector`. It writes no real external account and records a simulated artifact. A real Notion connector must add OAuth destination binding, account ownership checks, token handling, provider error mapping, and result verification before any live write is enabled.

## Logging and audit

Audit events record lifecycle facts such as upload, parse, summary generation, proposal creation, edit, approval, execution, and completion. They intentionally avoid source text and generated note bodies. Errors use safe domain messages.
