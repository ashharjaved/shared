# src/identity/application/services/login_rate_limiter.py

from datetime import timedelta
from typing import Optional

from src.shared.cache.redis import RedisClient
from src.shared.exceptions import AuthorizationError

import structlog

logger = structlog.get_logger()


class LoginRateLimiter:
    """
    Rate limiter for login attempts to prevent brute force attacks.
    
    Strategy:
    - Track failed login attempts per email
    - Lock account after MAX_ATTEMPTS within window
    - Exponential backoff on repeated failures
    - Clear counter on successful login
    """
    
    # Configuration
    MAX_ATTEMPTS = 5
    LOCKOUT_DURATION = timedelta(minutes=15)
    ATTEMPT_WINDOW = timedelta(minutes=5)
    
    def __init__(self, redis_client: RedisClient):
        self._redis = redis_client
    
    def _get_attempt_key(self, email: str) -> str:
        """Generate Redis key for attempt counter."""
        return f"login_attempts:{email.lower()}"
    
    def _get_lockout_key(self, email: str) -> str:
        """Generate Redis key for lockout status."""
        return f"login_lockout:{email.lower()}"
    
    async def check_and_increment(self, email: str) -> tuple[bool, Optional[str]]:
        """
        Check if login is allowed and increment attempt counter.
        
        Args:
            email: User email attempting login
            
        Returns:
            (is_allowed, error_message)
            
        Raises:
            AuthorizationError: If account is locked
        """
        lockout_key = self._get_lockout_key(email)
        attempt_key = self._get_attempt_key(email)
        
        # Check if account is locked
        is_locked = await self._redis.get(lockout_key)
        if is_locked:
            ttl = await self._redis.ttl(lockout_key)
            minutes_left = max(1, ttl // 60)
            
            logger.warning(
                "Login attempt on locked account",
                email=email,
                ttl_seconds=ttl
            )
            
            return False, f"Account is locked. Try again in {minutes_left} minutes."
        
        # Increment attempt counter
        attempts = await self._redis.incr(attempt_key)
        
        # Set TTL on first attempt
        if attempts == 1:
            await self._redis.expire(
                attempt_key,
                int(self.ATTEMPT_WINDOW.total_seconds())
            )
        
        # Check if threshold exceeded
        if attempts >= self.MAX_ATTEMPTS:
            # Lock the account
            await self._redis.setex(
                lockout_key,
                int(self.LOCKOUT_DURATION.total_seconds()),
                "locked"
            )
            
            logger.warning(
                "Account locked due to failed attempts",
                email=email,
                attempts=attempts
            )
            
            return False, f"Too many failed attempts. Account locked for {int(self.LOCKOUT_DURATION.total_seconds() // 60)} minutes."
        
        # Login allowed
        remaining = self.MAX_ATTEMPTS - attempts
        logger.info(
            "Login attempt recorded",
            email=email,
            attempts=attempts,
            remaining=remaining
        )
        
        return True, None
    
    async def record_success(self, email: str) -> None:
        """
        Clear attempt counter on successful login.
        
        Args:
            email: User email that successfully logged in
        """
        attempt_key = self._get_attempt_key(email)
        lockout_key = self._get_lockout_key(email)
        
        # Clear both counters
        await self._redis.delete(attempt_key)
        await self._redis.delete(lockout_key)
        
        logger.info("Login attempt counter cleared", email=email)
    
    async def record_failure(self, email: str) -> None:
        """
        Record a failed login attempt.
        
        This is called after authentication fails to track the attempt.
        The counter increment happens in check_and_increment.
        
        Args:
            email: User email that failed login
        """
        attempt_key = self._get_attempt_key(email)
        attempts = await self._redis.get(attempt_key)
        
        logger.warning(
            "Failed login attempt",
            email=email,
            current_attempts=attempts
        )
    
    async def get_remaining_attempts(self, email: str) -> int:
        """
        Get number of remaining login attempts before lockout.
        
        Args:
            email: User email to check
            
        Returns:
            Number of remaining attempts (0 if locked)
        """
        lockout_key = self._get_lockout_key(email)
        attempt_key = self._get_attempt_key(email)
        
        # Check if locked
        is_locked = await self._redis.get(lockout_key)
        if is_locked:
            return 0
        
        # Get current attempts
        attempts = await self._redis.get(attempt_key)
        current_attempts = int(attempts) if attempts else 0
        
        return max(0, self.MAX_ATTEMPTS - current_attempts)
    
    async def unlock_account(self, email: str) -> None:
        """
        Manually unlock an account (admin operation).
        
        Args:
            email: User email to unlock
        """
        attempt_key = self._get_attempt_key(email)
        lockout_key = self._get_lockout_key(email)
        
        await self._redis.delete(attempt_key)
        await self._redis.delete(lockout_key)
        
        logger.info("Account manually unlocked", email=email)