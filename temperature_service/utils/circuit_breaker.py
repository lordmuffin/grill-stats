"""
Circuit Breaker Pattern Implementation.

This module provides a circuit breaker implementation that prevents
calling services that are likely to fail, allowing them time to recover.
"""

import asyncio
import functools
import logging
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar, cast

# Type variable for return type of wrapped functions
T = TypeVar("T")

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests allowed
    OPEN = "open"  # Circuit is open, requests are not allowed
    HALF_OPEN = "half_open"  # Testing if service is back online


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open."""

    def __init__(self, service_name: str, last_failure: Optional[Exception] = None):
        """Initialize circuit breaker error."""
        self.service_name = service_name
        self.last_failure = last_failure
        message = f"Circuit breaker for {service_name} is open"
        if last_failure:
            message += f" due to: {str(last_failure)}"
        super().__init__(message)


class CircuitBreaker:
    """Circuit breaker implementation to prevent calling failing services."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        exception_types: tuple = (Exception,),
        excluded_exception_types: tuple = (),
    ):
        """Initialize circuit breaker.

        Args:
            name: Service name or identifier
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            exception_types: Exception types that should trip the circuit
            excluded_exception_types: Exception types to ignore when counting failures
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.exception_types = exception_types
        self.excluded_exception_types = excluded_exception_types

        # State
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.last_failure: Optional[Exception] = None

        logger.info(
            "Initialized circuit breaker for %s (threshold: %d, timeout: %d)", name, failure_threshold, recovery_timeout
        )

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorate a function with circuit breaker functionality."""

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            """Wrapper function implementing circuit breaking logic."""
            return self.call(func, *args, **kwargs)

        return wrapper

    def async_call(self) -> Callable[[Callable[..., T]], Callable[..., T]]:
        """Create an async decorator for circuit breaker."""

        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            """Decorate an async function with circuit breaker functionality."""

            @functools.wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> T:
                """Async wrapper function implementing circuit breaking logic."""
                return await self.call_async(func, *args, **kwargs)

            return cast(Callable[..., T], wrapper)

        return decorator

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute a function with circuit breaker protection."""
        self._check_state()

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.excluded_exception_types:
            # Don't count excluded exceptions as failures
            raise
        except self.exception_types as e:
            self._on_failure(e)
            raise

    async def call_async(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute an async function with circuit breaker protection."""
        self._check_state()

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.excluded_exception_types:
            # Don't count excluded exceptions as failures
            raise
        except self.exception_types as e:
            self._on_failure(e)
            raise

    def _check_state(self) -> None:
        """Check circuit state and raise error if open."""
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if self.last_failure_time and time.time() - self.last_failure_time >= self.recovery_timeout:
                logger.info(
                    "Circuit for %s transitioning from OPEN to HALF_OPEN after %d seconds", self.name, self.recovery_timeout
                )
                self.state = CircuitState.HALF_OPEN
            else:
                # Circuit is open, fail fast
                raise CircuitBreakerError(self.name, self.last_failure)

    def _on_success(self) -> None:
        """Handle successful call."""
        if self.state == CircuitState.HALF_OPEN:
            # Service is working again, reset circuit
            logger.info("Circuit for %s closed after successful test call", self.name)
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.last_failure = None
            self.last_failure_time = None

    def _on_failure(self, exception: Exception) -> None:
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure = exception
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN or self.failure_count >= self.failure_threshold:
            # Open the circuit on failure in HALF_OPEN or when threshold reached
            logger.warning(
                "Circuit for %s opened after %d failures. Last error: %s", self.name, self.failure_count, str(exception)
            )
            self.state = CircuitState.OPEN

    def reset(self) -> None:
        """Reset circuit to closed state."""
        logger.info("Circuit for %s manually reset", self.name)
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure = None
        self.last_failure_time = None

    def force_open(self) -> None:
        """Force circuit to open state."""
        logger.warning("Circuit for %s manually forced open", self.name)
        self.state = CircuitState.OPEN
        self.last_failure_time = time.time()

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed."""
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open."""
        return self.state == CircuitState.OPEN

    @property
    def status(self) -> Dict[str, Any]:
        """Get current circuit status."""
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": self.last_failure_time,
            "last_failure": str(self.last_failure) if self.last_failure else None,
        }


# Create async decorator
def async_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: int = 30,
    exception_types: tuple = (Exception,),
    excluded_exception_types: tuple = (),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Create an async circuit breaker decorator."""
    breaker = CircuitBreaker(name, failure_threshold, recovery_timeout, exception_types, excluded_exception_types)
    return breaker.async_call()


# Singleton registry of circuit breakers for global access
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str) -> Optional[CircuitBreaker]:
    """Get a circuit breaker by name."""
    return _circuit_breakers.get(name)


def register_circuit_breaker(breaker: CircuitBreaker) -> None:
    """Register a circuit breaker in the global registry."""
    _circuit_breakers[breaker.name] = breaker


def create_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: int = 30,
    exception_types: tuple = (Exception,),
    excluded_exception_types: tuple = (),
) -> CircuitBreaker:
    """Create and register a circuit breaker."""
    breaker = CircuitBreaker(name, failure_threshold, recovery_timeout, exception_types, excluded_exception_types)
    register_circuit_breaker(breaker)
    return breaker


def get_all_circuit_breakers() -> Dict[str, CircuitBreaker]:
    """Get all registered circuit breakers."""
    return _circuit_breakers.copy()


def reset_all_circuit_breakers() -> None:
    """Reset all registered circuit breakers."""
    for breaker in _circuit_breakers.values():
        breaker.reset()
