from app.domain.errors import DomainError


class UnsupportedDocumentType(DomainError):
    code = "UNSUPPORTED_DOCUMENT_TYPE"
    status_code = 415
    message = "Choose a PDF, DOCX, Markdown, or UTF-8 text file with a matching content type."


class DocumentTooLarge(DomainError):
    code = "DOCUMENT_TOO_LARGE"
    status_code = 413
    message = "The document exceeds the configured upload or extracted-content limit."


class DocumentEmpty(DomainError):
    code = "DOCUMENT_EMPTY"
    status_code = 422
    message = "The document is empty. Choose a document containing text."


class DocumentHasNoExtractableText(DocumentEmpty):
    code = "DOCUMENT_HAS_NO_EXTRACTABLE_TEXT"
    message = "This PDF has no extractable text. OCR is not supported; upload a text-based source."


class DocumentParseFailed(DomainError):
    code = "DOCUMENT_PARSE_FAILED"
    status_code = 422
    message = "The document could not be parsed. Check its format and upload a new copy."


class DocumentStorageUnavailable(DomainError):
    code = "DOCUMENT_STORAGE_UNAVAILABLE"
    status_code = 503
    message = "Source storage is unavailable. Try again later."
