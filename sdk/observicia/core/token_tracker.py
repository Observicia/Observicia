import threading
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional


@dataclass
class TokenUsage:
    """Tracks token usage for a specific session or request."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)


class TokenTracker:
    """Thread-safe token tracker for multiple LLM providers."""

    def __init__(self, retention_period: timedelta = timedelta(days=7)):
        self._lock = threading.Lock()
        self._retention_period = retention_period
        self._usage_by_provider: Dict[str,
                                      List[TokenUsage]] = defaultdict(list)
        self._stream_usage: Dict[str, TokenUsage] = {}

    def update(self, provider: str, prompt_tokens: int,
               completion_tokens: int) -> None:
        """Update token usage for a provider."""
        with self._lock:
            usage = TokenUsage(prompt_tokens=prompt_tokens,
                               completion_tokens=completion_tokens,
                               total_tokens=prompt_tokens + completion_tokens)
            self._usage_by_provider[provider].append(usage)
            self._cleanup_old_data(provider)

    def get_totals(self, provider: str) -> TokenUsage:
        """Retrieve total token usage for a provider."""
        with self._lock:
            total_usage = TokenUsage()
            for usage in self._usage_by_provider.get(provider, []):
                total_usage.prompt_tokens += usage.prompt_tokens
                total_usage.completion_tokens += usage.completion_tokens
                total_usage.total_tokens += usage.total_tokens
            return total_usage

    @contextmanager
    def stream_context(self, provider: str, session_id: str):
        """Context manager for streaming token tracking."""
        try:
            with self._lock:
                self._stream_usage[session_id] = TokenUsage()
            yield
        finally:
            with self._lock:
                if session_id in self._stream_usage:
                    final_usage = self._stream_usage[session_id]
                    self.update(provider, final_usage.prompt_tokens,
                                final_usage.completion_tokens)
                    del self._stream_usage[session_id]

    def get_usage(self,
                  provider: str,
                  window: Optional[timedelta] = None) -> Dict[str, int]:
        """Get token usage statistics for a provider."""
        with self._lock:
            usages = self._usage_by_provider[provider]
            if window:
                cutoff = datetime.utcnow() - window
                usages = [u for u in usages if u.timestamp >= cutoff]

            return {
                "prompt_tokens": sum(u.prompt_tokens for u in usages),
                "completion_tokens": sum(u.completion_tokens for u in usages),
                "total_tokens": sum(u.total_tokens for u in usages)
            }

    def get_usage_all_providers(
            self,
            window: Optional[timedelta] = None) -> Dict[str, Dict[str, int]]:
        """Get token usage statistics for all providers."""
        return {
            provider: self.get_usage(provider, window)
            for provider in self._usage_by_provider.keys()
        }

    def _cleanup_old_data(self, provider: str) -> None:
        """Remove data older than the retention period."""
        if provider not in self._usage_by_provider:
            return

        cutoff = datetime.utcnow() - self._retention_period
        self._usage_by_provider[provider] = [
            usage for usage in self._usage_by_provider[provider]
            if usage.timestamp >= cutoff
        ]
