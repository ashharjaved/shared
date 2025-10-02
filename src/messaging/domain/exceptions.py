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

class ChannelSuspendedError(WhatsAppDomainError):
    """Raised when attempting to use a suspended channel."""
    pass


class InvalidPhoneNumberError(WhatsAppDomainError):
    """Raised for invalid phone number format."""
    pass



class WebhookVerificationError(WhatsAppDomainError):
    """Raised when webhook verification fails."""
    pass

class RateLimitExceeded(WhatsAppDomainError):
    """Raised when WhatsApp API rate limit exceeded."""
    
    def __init__(self, error_code: str,error_message:str, retry_after: int):
        super().__init__(error_code, error_message)
        self.retry_after = retry_after


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


class ChannelNotFoundError(WhatsAppDomainError):
    """Channel does not exist."""
    pass


class ChannelInactiveError(WhatsAppDomainError):
    """Channel is not active."""
    pass


class MessageNotFoundError(WhatsAppDomainError):
    """Message does not exist."""
    pass


class TemplateNotFoundError(WhatsAppDomainError):
    """Template does not exist."""
    pass


class TemplateNotApprovedError(WhatsAppDomainError):
    """Template is not approved by WhatsApp."""
    pass


class DuplicateMessageError(WhatsAppDomainError):
    """Message already processed (idempotency violation)."""
    pass


class RateLimitExceededError(WhatsAppDomainError):
    """Rate limit exceeded for channel."""
    pass


class InvalidWebhookSignatureError(WhatsAppDomainError):
    """Webhook signature verification failed."""
    pass


class TranscriptionError(WhatsAppDomainError):
    """Voice transcription failed."""
    pass