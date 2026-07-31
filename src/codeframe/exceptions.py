"""Domain-specific exceptions that let the UI fail safely."""


class CodeframeError(Exception):
    """Base class for expected Codeframe failures."""


class ConfigurationError(CodeframeError):
    """Raised when workflow configuration is invalid."""


class DataValidationError(CodeframeError):
    """Raised when input data violates a notebook-derived contract."""


class ExternalServiceError(CodeframeError):
    """Raised when an external model service cannot complete safely."""


class TranslationUnresolvedError(ExternalServiceError):
    """Raised when any selected response remains untranslated."""


class NotebookParityError(CodeframeError):
    """Raised when the immutable notebook baseline differs."""
