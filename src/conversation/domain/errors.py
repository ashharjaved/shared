# Begin: src/conversation/domain/errors.py ***
from __future__ import annotations


class FlowNotFoundError(LookupError):
    """Raised when a menu flow cannot be found or is inactive."""
    pass


class InvalidSelectionError(ValueError):
    """Raised when the user selection cannot be resolved to a MenuOption."""
    pass


class SessionExpiredError(RuntimeError):
    """Raised when an operation is attempted on an expired session."""
    pass
# End: src/conversation/domain/errors.py ***
