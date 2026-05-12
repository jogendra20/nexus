import time
from collections import deque
from config import LIMITS

class RateLimiter:
    def __init__(self, provider: str):
        self.provider = provider
        self.max_calls = LIMITS[provider]["calls"]
        self.period = LIMITS[provider]["period"]
        self.calls = deque()

    def check(self) -> bool:
        now = time.time()
        while self.calls and now - self.calls[0] > self.period:
            self.calls.popleft()
        if len(self.calls) >= self.max_calls:
            return False
        self.calls.append(now)
        return True

    def remaining(self) -> int:
        now = time.time()
        while self.calls and now - self.calls[0] > self.period:
            self.calls.popleft()
        return self.max_calls - len(self.calls)

class LimiterManager:
    def __init__(self):
        self.limiters = {
            provider: RateLimiter(provider)
            for provider in LIMITS
        }

    def check(self, provider: str) -> bool:
        return self.limiters[provider].check()

    def status(self) -> dict:
        return {
            provider: self.limiters[provider].remaining()
            for provider in self.limiters
        }
