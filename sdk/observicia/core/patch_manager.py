import asyncio
from functools import wraps
from typing import Dict, Optional, Any
from contextlib import contextmanager

from observicia.core.context_manager import ObservabilityContext
from observicia.core.token_tracker import TokenTracker
from observicia.patchers import DEFAULT_PATCHERS


class PatchManager:
    """
    Manages patching and unpatching of LLM provider SDKs for token tracking and tracing.
    """

    def __init__(self) -> None:
        self._context = ObservabilityContext.get_current()
        self._token_tracker = TokenTracker()
        self._active_patches: Dict[str, Any] = {}
        self._original_functions: Dict[str, Any] = {}
        self._log_file = getattr(self._context, '_log_file', None)

    def patch_provider(self, provider_name: str) -> None:
        """
        Patch a specific LLM provider's SDK.
        
        Args:
            provider_name: Name of the LLM provider to patch (e.g., "openai", "anthropic")
        """
        if provider_name in self._active_patches:
            return  # Already patched

        patcher_class = DEFAULT_PATCHERS.get(provider_name)
        if not patcher_class:
            raise ValueError(f"Unsupported provider: {provider_name}")

        try:
            print(f"Patching {provider_name} SDK...")
            # Initialize patcher for this provider
            patcher = patcher_class(token_tracker=self._token_tracker,
                                    log_file=self._log_file,
                                    context=self._context)

            # Apply patches and store original functions
            orig_funcs = patcher.patch()
            self._original_functions[provider_name] = orig_funcs
            self._active_patches[provider_name] = patcher
            print(f"Patched {provider_name} SDK")

        except ImportError as e:
            raise ImportError(
                f"Could not patch {provider_name}. SDK not installed: {str(e)}"
            )
        except Exception as e:
            self._rollback_patches(provider_name)
            raise RuntimeError(f"Error patching {provider_name}: {str(e)}")

    def unpatch_provider(self, provider_name: str) -> None:
        """
        Remove patches for a specific provider.
        
        Args:
            provider_name: Name of the LLM provider to unpatch
        """
        if provider_name not in self._active_patches:
            return  # Not patched

        patcher = self._active_patches[provider_name]
        orig_funcs = self._original_functions[provider_name]

        try:
            patcher.unpatch(orig_funcs)
        finally:
            del self._active_patches[provider_name]
            del self._original_functions[provider_name]

    def patch_all(self) -> None:
        """Patch all supported LLM providers that are installed."""
        for provider in DEFAULT_PATCHERS.keys():
            try:
                self.patch_provider(provider)
            except ImportError:
                # Skip providers that aren't installed
                continue

    def unpatch_all(self) -> None:
        """Remove all active patches."""
        for provider in list(self._active_patches.keys()):
            self.unpatch_provider(provider)

    def _rollback_patches(self, provider_name: str) -> None:
        """Rollback patches for a provider if patching fails."""
        if provider_name in self._original_functions:
            patcher = self._active_patches.get(provider_name)
            if patcher:
                try:
                    patcher.unpatch(self._original_functions[provider_name])
                except Exception:
                    pass  # Best effort rollback
            del self._original_functions[provider_name]
            if provider_name in self._active_patches:
                del self._active_patches[provider_name]

    def __enter__(self):
        """Enable use as a context manager for automatic cleanup."""
        self.patch_all()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup when exiting context."""
        self.unpatch_all()
