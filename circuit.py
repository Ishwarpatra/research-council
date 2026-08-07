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

    async def record_success(self):
        async with self.lock:
            self.failure_count = 0
            self.state = "Closed"

    async def record_failure(self):
        trip_breaker = False
        async with self.lock:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold and self.state != "Open":
                self.state = "Open"
                self.last_state_change = time.time()
                trip_breaker = True

        # Fire webhook outside the lock as a non-blocking background task with strong references
        if trip_breaker:
            logger.warning("Primary provider circuit breaker tripped to OPEN.")
            task = asyncio.create_task(self._dispatch_webhook_alert("Primary provider circuit tripped to OPEN. Failing over to fallback."))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

    async def get_state(self):
        async with self.lock:
            if self.state == "Open" and (time.time() - self.last_state_change > self.recovery_timeout):
                self.state = "Half-Open"
            return self.state

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
