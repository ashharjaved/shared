# src/modules/whatsapp/domain/exceptions.py
"""
WhatsApp Domain Exceptions
"""


class WhatsAppDomainError(Exception):
    """Base exception for WhatsApp domain errors."""
    pass

class InvalidMessageContentError(WhatsAppDomainError):
    """Raised when message content is invalid."""
    pass


class CredentialNotFoundError(WhatsAppDomainError):
    """Raised when tenant credentials not configured."""
    pass


class ChannelNotFoundError(WhatsAppDomainError):
    """Raised when channel is not found."""
    pass


class ChannelSuspendedError(WhatsAppDomainError):
    """Raised when attempting to use a suspended channel."""
    pass


class InvalidPhoneNumberError(WhatsAppDomainError):
    """Raised for invalid phone number format."""
    pass


class MessageNotFoundError(WhatsAppDomainError):
    """Raised when message is not found."""
    pass


class DuplicateMessageError(WhatsAppDomainError):
    """Raised when duplicate message is detected."""
    pass


class RateLimitExceededError(WhatsAppDomainError):
    """Raised when rate limit is exceeded."""
    pass


class WebhookVerificationError(WhatsAppDomainError):
    """Raised when webhook verification fails."""
    pass

class RateLimitExceeded(WhatsAppDomainError):
    """Raised when WhatsApp API rate limit exceeded."""
    
    def __init__(self, error_code: str,error_message:str, retry_after: int):
        super().__init__(error_code, error_message)
        self.retry_after = retry_after

class InvalidWebhookSignatureError(WhatsAppDomainError):
    """Raised when webhook signature is invalid."""
    pass

class TemporaryFailure(WhatsAppDomainError):
    """Raised on transient failures that may recover."""
    
    def __init__(self, error_code: str, error_message: str):
        super().__init__(error_code, error_message)


class PermanentFailure(WhatsAppDomainError):
    """Raised on permanent failures that won't recover with retry."""
    
    def __init__(self, error_code: str, error_message: str):
        super().__init__(error_code, error_message)

class WhatsAppAPIError(WhatsAppDomainError):
    """Raised for WhatsApp API errors."""
    
    def __init__(self, error_code: str, error_message: str, error_data: dict | None = None) -> None:
        self.error_code = error_code
        self.error_message = error_message
        self.error_data = error_data or {}
        super().__init__(f"WhatsApp API Error {error_code}: {error_message}")