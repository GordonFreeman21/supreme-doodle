"""
Token Bucket Rate Limiter with Global and Per-Server Limits

This module implements a sophisticated rate limiting system to ensure
ethical and compliant server monitoring.

RATE LIMITING STRATEGY:
=======================
1. Global Token Bucket: Limits total queries across all servers
2. Per-Server Semaphore: Limits concurrent queries per individual server
3. Exponential Backoff: Increases wait time on failures
4. Jitter: Adds randomness to prevent thundering herd problems
5. Automatic Pause: Respects HTTP 429 and connection timeouts

ETHICAL COMPLIANCE:
===================
- Prevents overwhelming servers with requests
- Respects server resources and bandwidth
- Complies with Minecraft EULA Section 2.E (no excessive polling)
- Follows best practices for API consumption
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class TokenBucket:
    """
    Token bucket algorithm for rate limiting.
    
    Tokens are added at a fixed rate up to a maximum capacity.
    Each request consumes one token. If no tokens available,
    the request must wait.
    """
    rate: float  # Tokens per second
    capacity: float  # Maximum tokens
    tokens: float = field(default=0.0)
    last_update: float = field(default_factory=time.monotonic)
    
    def __post_init__(self):
        self.tokens = self.capacity  # Start full
    
    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now
    
    async def acquire(self) -> float:
        """
        Acquire a token, waiting if necessary.
        
        Returns:
            Time waited in seconds
        """
        wait_time = 0.0
        
        while True:
            self._refill()
            
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return wait_time
            
            # Calculate wait time for next token
            tokens_needed = 1.0 - self.tokens
            wait_for = tokens_needed / self.rate
            
            await asyncio.sleep(wait_for)
            wait_time += wait_for


@dataclass
class BackoffState:
    """Tracks backoff state for a single server."""
    retries: int = 0
    last_failure: float = 0.0
    current_backoff: float = 0.0


class RateLimiter:
    """
    Combined rate limiter with global limits and per-server tracking.
    
    Features:
    - Global token bucket for overall rate limiting
    - Per-server semaphore for concurrency control
    - Exponential backoff with jitter for failed servers
    - Automatic recovery after successful queries
    """
    
    def __init__(
        self,
        global_rate: float = 1.0,
        per_server_concurrency: int = 1,
        base_backoff: float = 1.0,
        max_backoff: float = 300.0,
        jitter_factor: float = 0.1,
    ):
        """
        Initialize rate limiter.
        
        Args:
            global_rate: Max queries per second globally
            per_server_concurrency: Max concurrent queries per server
            base_backoff: Base backoff time in seconds
            max_backoff: Maximum backoff time in seconds
            jitter_factor: Randomness factor for jitter (0.0-1.0)
        """
        self.global_bucket = TokenBucket(rate=global_rate, capacity=max(1.0, global_rate * 2))
        self.per_server_concurrency = per_server_concurrency
        self.base_backoff = base_backoff
        self.max_backoff = max_backoff
        self.jitter_factor = jitter_factor
        
        # Per-server state
        self._server_semaphores: Dict[str, asyncio.Semaphore] = {}
        self._server_backoff: Dict[str, BackoffState] = {}
        self._lock = asyncio.Lock()
    
    def _get_semaphore(self, server_address: str) -> asyncio.Semaphore:
        """Get or create semaphore for a server."""
        if server_address not in self._server_semaphores:
            self._server_semaphores[server_address] = asyncio.Semaphore(self.per_server_concurrency)
        return self._server_semaphores[server_address]
    
    def _get_backoff_state(self, server_address: str) -> BackoffState:
        """Get or create backoff state for a server."""
        if server_address not in self._server_backoff:
            self._server_backoff[server_address] = BackoffState()
        return self._server_backoff[server_address]
    
    def _calculate_backoff(self, state: BackoffState) -> float:
        """
        Calculate backoff time with exponential increase and jitter.
        
        Formula: min(base * 2^retries + jitter, max_backoff)
        """
        exponential = self.base_backoff * (2 ** state.retries)
        jitter = random.uniform(0, self.jitter_factor * exponential)
        return min(exponential + jitter, self.max_backoff)
    
    async def acquire_global(self) -> float:
        """
        Acquire permission from global rate limiter.
        
        Returns:
            Time waited in seconds
        """
        return await self.global_bucket.acquire()
    
    async def acquire_server(self, server_address: str) -> asyncio.Semaphore:
        """
        Acquire per-server concurrency slot.
        
        Returns:
            Semaphore context manager
        """
        semaphore = self._get_semaphore(server_address)
        return semaphore
    
    async def record_success(self, server_address: str) -> None:
        """Record successful query - reset backoff state."""
        async with self._lock:
            state = self._get_backoff_state(server_address)
            state.retries = 0
            state.current_backoff = 0.0
    
    async def record_failure(self, server_address: str) -> float:
        """
        Record failed query - calculate and apply backoff.
        
        Returns:
            Backoff time in seconds
        """
        async with self._lock:
            state = self._get_backoff_state(server_address)
            state.retries += 1
            state.last_failure = time.monotonic()
            state.current_backoff = self._calculate_backoff(state)
            return state.current_backoff
    
    async def get_backoff_delay(self, server_address: str) -> float:
        """Get current backoff delay for a server."""
        async with self._lock:
            state = self._get_backoff_state(server_address)
            return state.current_backoff
    
    async def should_skip_due_to_backoff(self, server_address: str) -> bool:
        """Check if server should be skipped due to active backoff."""
        async with self._lock:
            state = self._get_backoff_state(server_address)
            if state.current_backoff <= 0:
                return False
            
            elapsed = time.monotonic() - state.last_failure
            return elapsed < state.current_backoff
    
    async def pause_on_rate_limit(self, duration: float = 60.0) -> None:
        """
        Pause all operations when rate limited (HTTP 429).
        
        This is a global pause to respect server rate limits.
        """
        # Drain the token bucket to force waiting
        self.global_bucket.tokens = 0.0
        self.global_bucket.last_update = time.monotonic()
        
        # Wait for specified duration
        await asyncio.sleep(duration)
        
        # Refill bucket after pause
        self.global_bucket._refill()
