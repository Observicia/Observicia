import asyncio
from functools import wraps
from typing import Any, AsyncIterator, Generator

from ..core.context_manager import ObservabilityContext
from ..core.token_tracker import TokenTracker
from ..utils.helpers import count_tokens


class LiteLLMPatcher:
    """
    Patcher for LiteLLM's API that adds tracing, token tracking, and policy enforcement.

    Features:
    - Tracing with OpenTelemetry
    - Token tracking for prompt and response
    - Policy enforcement
    - Streaming support
    """

    def __init__(self,
                 token_tracker: TokenTracker = None,
                 log_file: Any = None,
                 context: ObservabilityContext = None):
        self._original_functions = {}
        self._token_tracker = token_tracker or TokenTracker()
        self._context = context or ObservabilityContext.get_current()

    def patch(self) -> None:
        """
        Patch LiteLLM's SDK functions.
        """
        try:
            import litellm

            pass

        except ImportError:
            raise ImportError("LiteLLM SDK is not installed.")

    def unpatch(self) -> None:
        """
        Restore original LiteLLM SDK functions.
        """
        try:
            import litellm

            pass

        except ImportError:
            raise ImportError("LiteLLM SDK is not installed.")
