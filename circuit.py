import asyncio
import logging
import time

import httpx

logger = logging.getLogger("rcc.circuit")

class CircuitBreaker:
    def __init__(self, failure_threshold=3, recovery_timeout=60, webhook_url=None):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.webhook_url = webhook_url
        self.state = "Closed"
        self.failure_count = 0
        self.last_state_change = time.time()
        self.lock = asyncio.Lock()
        self._background_tasks = set()
        self.state_change_callbacks = []  # List of callbacks: callback(new_state: str, message: str)

    def register_callback(self, callback):
        """Register a callback to be fired on state transition."""
        self.state_change_callbacks.append(callback)

    async def _notify_callbacks(self, new_state: str, message: str):
        """Invoke all registered callbacks in a safe manner."""
        for cb in self.state_change_callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(new_state, message)
                else:
                    cb(new_state, message)
            except Exception as e:
                logger.error(f"Error in circuit breaker callback: {e}")

    async def record_success(self):
        state_changed = False
        async with self.lock:
            if self.state != "Closed":
                self.state = "Closed"
                self.last_state_change = time.time()
                state_changed = True
            self.failure_count = 0

        if state_changed:
            msg = "Primary LLM provider connection recovered. Circuit breaker CLOSED."
            logger.info(msg)
            await self._notify_callbacks("Closed", msg)

    async def record_failure(self):
        trip_breaker = False
        async with self.lock:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold and self.state != "Open":
                self.state = "Open"
                self.last_state_change = time.time()
                trip_breaker = True

        if trip_breaker:
            from config import settings
            msg = f"Primary LLM provider connection failed ({self.failure_count} failures). Circuit breaker tripped to OPEN. Failing over to fallback: {settings.fallback_provider}."
            logger.warning(msg)
            # Fire webhook outside the lock as a non-blocking background task with strong references
            task = asyncio.create_task(self._dispatch_webhook_alert(msg))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
            
            await self._notify_callbacks("Open", msg)

    async def get_state(self):
        state_changed = False
        current_state = "Closed"
        async with self.lock:
            if self.state == "Open" and (time.time() - self.last_state_change > self.recovery_timeout):
                self.state = "Half-Open"
                self.last_state_change = time.time()
                state_changed = True
            current_state = self.state

        if state_changed:
            msg = "Circuit breaker testing connection in HALF-OPEN state."
            logger.info(msg)
            await self._notify_callbacks("Half-Open", msg)

        return current_state

    async def _dispatch_webhook_alert(self, message: str):
        if not self.webhook_url:
            return
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    self.webhook_url,
                    json={"text": f"[RCC System Alert] {message}"},
                    timeout=5.0
                )
        except Exception as e:
            logger.error(f"Failed to dispatch webhook alert: {e}")
