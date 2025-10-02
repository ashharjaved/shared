"""
WhatsApp Business API Gateway Implementation
Implements: DEV-2 WhatsApp Channel with Circuit Breaker, Retry, Rate Limiting
"""

import hashlib
import hmac
import asyncio
from typing import Dict, Any, List, Optional
from enum import Enum
from datetime import datetime
from functools import wraps

import httpx
from httpx import AsyncClient, HTTPStatusError, RequestError, HTTPError

from src.messaging.domain.protocols import WhatsAppGateway
from src.messaging.domain.exceptions import (
    WhatsAppAPIError,
    RateLimitExceeded,
    TemporaryFailure,
    PermanentFailure
)
from shared.infrastructure.observability.logger import get_logger
from shared.infrastructure.observability.metrics import MetricsCollector
from shared.infrastructure.observability.tracer import get_tracer

logger = get_logger(__name__)
metrics = MetricsCollector()
tracer = get_tracer()


def trace_method(func):
    """Decorator for tracing async methods."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        trace_id = tracer.start_span(func.__name__)
        try:
            result = await func(*args, **kwargs)
            tracer.end_span(trace_id, status="success")
            return result
        except Exception as e:
            tracer.end_span(trace_id, status="error", error=str(e))
            raise
    return wrapper


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit Breaker pattern for WhatsApp API calls.
    Prevents cascading failures by failing fast when service is down.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type[Exception] = HTTPError
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            expected_exception: Exception type to catch
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitState.CLOSED
    
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker entering HALF_OPEN state")
            else:
                raise TemporaryFailure(
                    error_code="circuit_breaker_open",
                    error_message="Circuit breaker OPEN - WhatsApp API unavailable"
                )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    async def call_async(self, func, *args, **kwargs):
        """Execute async function with circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker entering HALF_OPEN state")
            else:
                raise TemporaryFailure(
                    error_code="circuit_breaker_open",
                    error_message="Circuit breaker OPEN - WhatsApp API unavailable"
                )
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self.last_failure_time is None:
            return False
        return (
            datetime.utcnow() - self.last_failure_time
        ).total_seconds() >= self.recovery_timeout
    
    def _on_success(self):
        """Reset failure count on successful call."""
        if self.state == CircuitState.HALF_OPEN:
            logger.info("Circuit breaker recovered - entering CLOSED state")
        self.failure_count = 0
        self.state = CircuitState.CLOSED
    
    def _on_failure(self):
        """Increment failure count and open circuit if threshold reached."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error(
                f"Circuit breaker OPEN after {self.failure_count} failures"
            )
            metrics.increment_counter("whatsapp.circuit_breaker.opened")


class WhatsAppGatewayImpl(WhatsAppGateway):
    """
    WhatsApp Business API gateway implementation.
    
    Implements:
    - Circuit Breaker pattern for fault tolerance
    - Exponential backoff retry logic
    - Rate limit handling with Retry-After
    - Comprehensive error mapping
    - Observability (tracing, metrics, structured logging)
    """
    
    # Meta API error codes mapping
    RETRIABLE_ERROR_CODES = {
        1, 2, 4, 17, 32, 613,  # Temporary/rate limit errors
    }
    
    PERMANENT_ERROR_CODES = {
        100, 190, 131009,  # Auth/permission errors
    }
    
    def __init__(
        self,
        base_url: str = "https://graph.facebook.com/v18.0",
        max_retries: int = 3,
        initial_retry_delay: float = 1.0,
        timeout: float = 30.0
    ):
        """
        Initialize WhatsApp gateway.
        
        Args:
            base_url: Meta Graph API base URL
            max_retries: Maximum retry attempts for transient failures
            initial_retry_delay: Initial delay for exponential backoff (seconds)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay
        
        self.client = AsyncClient(
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(
                max_keepalive_connections=100,
                max_connections=200
            )
        )
        
        # Circuit breaker for fault tolerance
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
            expected_exception=HTTPError
        )
    
    @trace_method
    async def send_message(
        self,
        phone_number_id: str,
        to: str,
        message_type: str,
        content: Dict[str, Any],
        access_token: str
    ) -> Dict[str, Any]:
        """
        Send a message via WhatsApp API with retry logic.
        
        Args:
            phone_number_id: WhatsApp Business phone number ID
            to: Recipient phone number (E.164 format)
            message_type: Message type (text, template, image, etc.)
            content: Message content based on type
            access_token: WhatsApp Business API access token
            
        Returns:
            API response with message ID
            
        Raises:
            WhatsAppAPIError: On API errors
            RateLimitExceeded: When rate limited
            TemporaryFailure: On transient failures
            PermanentFailure: On permanent errors
        """
        metrics.increment_counter("whatsapp.send_message.attempt")
        
        # Build payload
        payload = self._build_payload(
            to=to,
            message_type=message_type,
            content=content
        )
        
        # Execute with circuit breaker and retry
        return await self._execute_with_retry(
            method="POST",
            url=f"{self.base_url}/{phone_number_id}/messages",
            payload=payload,
            access_token=access_token
        )
    
    @trace_method
    async def send_template_message(
        self,
        phone_number_id: str,
        to: str,
        template_name: str,
        language_code: str,
        components: List[Dict[str, Any]],
        access_token: str
    ) -> Dict[str, Any]:
        """Send a pre-approved template message."""
        content = {
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": components
            }
        }
        
        return await self.send_message(
            phone_number_id=phone_number_id,
            to=to,
            message_type="template",
            content=content,
            access_token=access_token
        )
    
    @trace_method
    async def get_media_url(
        self,
        media_id: str,
        access_token: str
    ) -> str:
        """
        Get media download URL.
        
        Args:
            media_id: WhatsApp media ID
            access_token: API access token
            
        Returns:
            Media download URL
        """
        result = await self._execute_with_retry(
            method="GET",
            url=f"{self.base_url}/{media_id}",
            payload=None,
            access_token=access_token
        )
        
        return result.get("url", "")
    
    @trace_method
    async def download_media(
        self,
        media_url: str,
        access_token: str
    ) -> bytes:
        """
        Download media file.
        
        Args:
            media_url: Full media download URL
            access_token: API access token
            
        Returns:
            Media file bytes
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        
        try:
            response = await self.client.get(media_url, headers=headers)
            response.raise_for_status()
            
            metrics.increment_counter("whatsapp.download_media.success")
            return response.content
            
        except HTTPStatusError as e:
            logger.error(f"Failed to download media: {e}")
            metrics.increment_counter("whatsapp.download_media.error")
            raise WhatsAppAPIError(
                error_code="media_download_error",
                error_message=f"Failed to download media: {e}"
            )
    
    @trace_method
    async def upload_media(
        self,
        phone_number_id: str,
        file_data: bytes,
        mime_type: str,
        access_token: str
    ) -> str:
        """
        Upload media and get media ID.
        
        Args:
            phone_number_id: WhatsApp Business phone number ID
            file_data: File content bytes
            mime_type: MIME type (e.g., image/jpeg)
            access_token: API access token
            
        Returns:
            Media ID
        """
        url = f"{self.base_url}/{phone_number_id}/media"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        files = {
            "file": ("file", file_data, mime_type),
            "messaging_product": (None, "whatsapp"),
            "type": (None, mime_type.split("/")[0])
        }
        
        try:
            response = await self.client.post(url, files=files, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            media_id = data.get("id", "")
            
            logger.info(f"Media uploaded successfully: {media_id}")
            metrics.increment_counter("whatsapp.upload_media.success")
            
            return media_id
            
        except HTTPStatusError as e:
            logger.error(f"Failed to upload media: {e}")
            metrics.increment_counter("whatsapp.upload_media.error")
            raise WhatsAppAPIError(
                error_code="media_upload_error",
                error_message=f"Failed to upload media: {e}"
            )
    
    def _build_payload(
        self,
        to: str,
        message_type: str,
        content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build WhatsApp API message payload.
        
        Args:
            to: Recipient phone number
            message_type: Message type
            content: Type-specific content
            
        Returns:
            Complete API payload
        """
        payload: Dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": message_type
        }
        
        # Merge content into payload
        payload.update(content)
        
        return payload
    
    async def _execute_with_retry(
        self,
        method: str,
        url: str,
        payload: Optional[Dict[str, Any]],
        access_token: str
    ) -> Dict[str, Any]:
        """
        Execute API call with circuit breaker and exponential backoff retry.
        
        Args:
            method: HTTP method (GET, POST)
            url: Full API URL
            payload: Request payload (None for GET)
            access_token: API access token
            
        Returns:
            API response data
            
        Raises:
            RateLimitExceeded: When rate limited
            TemporaryFailure: On transient failures after retries
            PermanentFailure: On permanent errors
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        last_exception: Optional[Exception] = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # Execute with circuit breaker
                result = await self.circuit_breaker.call_async(
                    self._make_request,
                    method=method,
                    url=url,
                    payload=payload,
                    headers=headers
                )
                
                metrics.increment_counter("whatsapp.api_call.success")
                return result
                
            except HTTPStatusError as e:
                last_exception = e
                
                # Parse error response
                error_data = self._parse_error_response(e.response)
                error_code = error_data.get("code")
                error_message = error_data.get("message", "Unknown error")
                
                logger.warning(
                    f"WhatsApp API error (attempt {attempt + 1}/{self.max_retries + 1})",
                    extra={
                        "status_code": e.response.status_code,
                        "error_code": error_code,
                        "error_message": error_message,
                    }
                )
                
                # Handle rate limiting (429 or specific error codes)
                if e.response.status_code == 429 or error_code in {4, 80007}:
                    retry_after = self._get_retry_after(e.response)
                    metrics.increment_counter("whatsapp.api_call.rate_limited")
                    
                    raise RateLimitExceeded(
                        error_message=f"Rate limited by WhatsApp API. Retry after {retry_after}s",
                        retry_after=retry_after,error_code=""
                    )
                
                # Permanent errors - don't retry
                if error_code in self.PERMANENT_ERROR_CODES:
                    metrics.increment_counter("whatsapp.api_call.permanent_error")
                    raise PermanentFailure(
                        error_code=str(error_code),
                        error_message=error_message
                    )
                
                # Retriable errors - apply exponential backoff
                if error_code in self.RETRIABLE_ERROR_CODES:
                    if attempt < self.max_retries:
                        delay = self._calculate_backoff(attempt)
                        logger.info(f"Retrying after {delay}s...")
                        await asyncio.sleep(delay)
                        continue
                
                # Unknown error - retry with backoff
                if attempt < self.max_retries:
                    delay = self._calculate_backoff(attempt)
                    logger.info(f"Retrying unknown error after {delay}s...")
                    await asyncio.sleep(delay)
                    continue
                
                # Max retries exceeded
                metrics.increment_counter("whatsapp.api_call.max_retries_exceeded")
                raise TemporaryFailure(
                    error_code=str(error_code),
                    error_message=f"Max retries exceeded: {error_message}"
                )
                
            except RequestError as e:
                last_exception = e
                logger.error(f"Network error (attempt {attempt + 1}): {e}")
                
                if attempt < self.max_retries:
                    delay = self._calculate_backoff(attempt)
                    await asyncio.sleep(delay)
                    continue
                
                metrics.increment_counter("whatsapp.api_call.network_error")
                raise TemporaryFailure(
                    error_code="network_error",
                    error_message=f"Network error after {self.max_retries} retries: {str(e)}"
                )
        
        # Should not reach here, but fallback
        raise TemporaryFailure(
            error_code="unknown_error",
            error_message=f"Failed after {self.max_retries} retries: {str(last_exception)}"
        )
    
    async def _make_request(
        self,
        method: str,
        url: str,
        payload: Optional[Dict[str, Any]],
        headers: Dict[str, str]
    ) -> Dict[str, Any]:
        """Make HTTP request to WhatsApp API."""
        if method == "GET":
            response = await self.client.get(url, headers=headers)
        elif method == "POST":
            response = await self.client.post(url, json=payload, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        response.raise_for_status()
        return response.json()
    
    def _parse_error_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Parse error response from WhatsApp API."""
        try:
            data = response.json()
            return data.get("error", {})
        except Exception:
            return {
                "code": "unknown",
                "message": response.text[:200]
            }
    
    def _get_retry_after(self, response: httpx.Response) -> int:
        """
        Extract Retry-After header value.
        
        Per AC-2.3.8: Honor Retry-After header on 429 responses.
        
        Args:
            response: HTTP response
            
        Returns:
            Retry delay in seconds (default 60)
        """
        retry_after = response.headers.get("Retry-After", "60")
        try:
            return int(retry_after)
        except ValueError:
            # Could be HTTP-date format, fallback to default
            return 60
    
    def _calculate_backoff(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay.
        
        Formula: initial_delay * (2 ^ attempt)
        Max delay capped at 60 seconds.
        
        Args:
            attempt: Current attempt number (0-indexed)
            
        Returns:
            Delay in seconds
        """
        delay = self.initial_retry_delay * (2 ** attempt)
        return min(delay, 60.0)  # Cap at 60 seconds
    
    @staticmethod
    def verify_webhook_signature(
        payload: bytes,
        signature: str,
        app_secret: str
    ) -> bool:
        """
        Verify webhook signature from Meta.
        
        Per AC-2.1.1: Verify SHA256 HMAC signature.
        
        Args:
            payload: Raw webhook payload bytes
            signature: X-Hub-Signature-256 header value
            app_secret: WhatsApp app secret
            
        Returns:
            True if signature valid, False otherwise
        """
        expected_signature = hmac.new(
            app_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Signature format: "sha256=<hash>"
        provided_hash = signature.replace("sha256=", "")
        
        is_valid = hmac.compare_digest(expected_signature, provided_hash)
        
        if not is_valid:
            logger.warning("Webhook signature verification failed")
            metrics.increment_counter("whatsapp.webhook.signature_invalid")
        
        return is_valid
    
    async def close(self):
        """Close the HTTP client connection pool."""
        await self.client.aclose()
        logger.info("WhatsApp gateway client closed")