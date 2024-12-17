from typing import Any, Dict, AsyncIterator, Generator
from functools import wraps
from inspect import getfullargspec

from ..core.context_manager import ObservabilityContext
from ..core.token_tracker import TokenTracker
from ..utils.tracing_helpers import start_llm_span
from ..utils.token_helpers import count_text_tokens, update_token_usage
from ..utils.policy_helpers import enforce_policies
from ..utils.stream_helpers import handle_stream, handle_async_stream


class OllamaPatcher:
    """
    Patcher for Ollama's Python SDK that adds tracing, token tracking, and policy enforcement.
    
    Features:
    - Tracing with OpenTelemetry
    - Token tracking for prompt and response
    - Policy enforcement
    - Support for both sync and async APIs
    """

    def __init__(self,
                 token_tracker: TokenTracker = None,
                 log_file: Any = None,
                 context: ObservabilityContext = None):
        self._original_functions = {}
        self._token_tracker = token_tracker or TokenTracker()
        self._context = context or ObservabilityContext.get_current()
        self._patched = False
        self.logger = self._context._logger if hasattr(self._context,
                                                       '_logger') else None

    def patch(self) -> Dict[str, Any]:
        """Apply patches to Ollama SDK functions."""
        if self._patched:
            return self._original_functions

        try:
            import ollama
            # Store original functions from the module level
            original_functions = {
                'generate': ollama.generate,
                'chat': ollama.chat,
                'embed': ollama.embed,
                # Client methods
                'client_generate': ollama.Client.generate,
                'client_chat': ollama.Client.chat,
                'client_embed': ollama.Client.embed,
                # AsyncClient methods
                'async_client_generate': ollama.AsyncClient.generate,
                'async_client_chat': ollama.AsyncClient.chat,
                'async_client_embed': ollama.AsyncClient.embed,
            }

            # Patch module-level functions
            ollama.generate = self._wrap_generate(ollama.generate)
            ollama.chat = self._wrap_chat(ollama.chat)
            ollama.embed = self._wrap_embed(ollama.embed)

            # Patch Client methods
            ollama.Client.generate = self._wrap_generate(
                ollama.Client.generate)
            ollama.Client.chat = self._wrap_chat(ollama.Client.chat)
            ollama.Client.embed = self._wrap_embed(ollama.Client.embed)

            # Patch AsyncClient methods
            ollama.AsyncClient.generate = self._wrap_async_generate(
                ollama.AsyncClient.generate)
            ollama.AsyncClient.chat = self._wrap_async_chat(
                ollama.AsyncClient.chat)
            ollama.AsyncClient.embed = self._wrap_async_embed(
                ollama.AsyncClient.embed)

            self._original_functions = original_functions
            self._patched = True
            return original_functions

        except ImportError as e:
            raise ImportError(f"Ollama SDK not installed: {str(e)}")
        except Exception as e:
            self._rollback_patches()
            raise RuntimeError(f"Error patching Ollama SDK: {str(e)}")

    def unpatch(self, original_functions: Dict[str, Any] = None) -> None:
        """Restore original Ollama SDK functions."""
        if not self._patched:
            return

        try:
            import ollama
            original_functions = original_functions or self._original_functions

            # Restore module-level functions
            ollama.generate = original_functions['generate']
            ollama.chat = original_functions['chat']
            ollama.embed = original_functions['embed']

            # Restore Client methods
            ollama.Client.generate = original_functions['client_generate']
            ollama.Client.chat = original_functions['client_chat']
            ollama.Client.embed = original_functions['client_embed']

            # Restore AsyncClient methods
            ollama.AsyncClient.generate = original_functions[
                'async_client_generate']
            ollama.AsyncClient.chat = original_functions['async_client_chat']
            ollama.AsyncClient.embed = original_functions['async_client_embed']

            self._patched = False
            self._original_functions = {}

        except Exception as e:
            raise RuntimeError(f"Error unpatching Ollama SDK: {str(e)}")

    def _rollback_patches(self) -> None:
        """Rollback patches if patching fails."""
        self.unpatch()

    def _is_method(self, func: Any) -> bool:
        """Check if a function is an instance method by looking at its arguments."""
        try:
            return 'self' in getfullargspec(func).args
        except Exception:
            return False

    def _wrap_generate(self, func: Any) -> Any:
        """Wrap generate with tracing and token tracking."""
        is_method = self._is_method(func)

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract actual args based on whether this is a method
            actual_kwargs = kwargs.copy()
            if is_method and len(args) > 0:
                client_self = args[0]
                other_args = args[1:]
                if len(other_args) >= 1:
                    actual_kwargs['model'] = other_args[0]
                if len(other_args) >= 2:
                    actual_kwargs['prompt'] = other_args[1]
            else:
                actual_kwargs.update(dict(zip(['model', 'prompt'], args)))

            with start_llm_span("ollama.generate", {
                    'model': actual_kwargs.get('model', ''),
                    'provider': 'ollama'
            }) as span:
                self.logger.info("Starting generate request",
                                 extra={"model": actual_kwargs.get('model')})
                try:
                    prompt = actual_kwargs.get('prompt', '')
                    model = actual_kwargs.get('model', '')
                    prompt_tokens = count_text_tokens(prompt, model)
                    span.set_attribute("prompt.tokens", prompt_tokens)

                    if actual_kwargs.get('stream', False):
                        return handle_stream(func,
                                             None,
                                             span,
                                             prompt_tokens,
                                             self._token_tracker,
                                             self._context,
                                             prompt=prompt,
                                             *args,
                                             **kwargs)

                    response = func(*args, **kwargs)
                    completion = response.get('response', '')
                    completion_tokens = count_text_tokens(completion, model)

                    span.set_attributes({
                        "completion.tokens": completion_tokens,
                        "total.tokens": prompt_tokens + completion_tokens,
                        "model": model
                    })

                    update_token_usage(
                        self._token_tracker, "ollama", {
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": prompt_tokens + completion_tokens
                        })

                    if self._context and self._context.policy_engine:
                        enforce_policies(self._context,
                                         span,
                                         response,
                                         prompt=prompt,
                                         completion=completion)

                    return response

                except Exception as e:
                    span.record_exception(e)
                    raise

        return wrapper

    def _wrap_chat(self, func: Any) -> Any:
        """Wrap chat with tracing and token tracking."""
        is_method = self._is_method(func)

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract actual args based on whether this is a method
            actual_kwargs = kwargs.copy()
            if is_method and len(args) > 0:
                client_self = args[0]
                other_args = args[1:]
                if len(other_args) >= 1:
                    actual_kwargs['model'] = other_args[0]
                if len(other_args) >= 2:
                    actual_kwargs['messages'] = other_args[1]
            else:
                actual_kwargs.update(dict(zip(['model', 'messages'], args)))

            with start_llm_span("ollama.chat", actual_kwargs) as span:
                self.logger.info("Starting chat request",
                                 extra={"model": actual_kwargs.get('model')})
                try:
                    messages = actual_kwargs.get('messages', [])
                    model = actual_kwargs.get('model', '')
                    prompt = messages[-1].get('content',
                                              '') if messages else ''
                    prompt_tokens = sum(
                        count_text_tokens(msg.get('content', ''), model)
                        for msg in messages or [])
                    span.set_attribute("prompt.tokens", prompt_tokens)

                    if actual_kwargs.get('stream', False):
                        return handle_stream(func,
                                             None,
                                             span,
                                             prompt_tokens,
                                             self._token_tracker,
                                             self._context,
                                             prompt=prompt,
                                             *args,
                                             **kwargs)

                    response = func(*args, **kwargs)
                    completion = response.get('message', {}).get('content', '')
                    completion_tokens = count_text_tokens(completion, model)

                    span.set_attributes({
                        "completion.tokens": completion_tokens,
                        "total.tokens": prompt_tokens + completion_tokens,
                        "model": model
                    })

                    self._token_tracker.update(
                        "ollama",
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens)

                    if self._context and self._context.policy_engine:
                        enforce_policies(self._context,
                                         span,
                                         response,
                                         prompt=prompt,
                                         completion=completion)

                    return response

                except Exception as e:
                    span.record_exception(e)
                    raise

        return wrapper

    def _wrap_async_generate(self, func: Any) -> Any:
        """Wrap async generate with tracing and token tracking."""

        @wraps(func)
        async def wrapper(client_self: Any,
                          model: str = '',
                          prompt: str = '',
                          **kwargs: Any) -> Any:
            with start_llm_span("ollama.generate.async", kwargs) as span:
                self.logger.info("Starting async generate request",
                                 extra={"model": model})
                try:
                    prompt_tokens = count_text_tokens(prompt, model)
                    span.set_attribute("prompt.tokens", prompt_tokens)

                    if kwargs.get('stream', False):
                        return await handle_async_stream(func,
                                                         client_self,
                                                         span,
                                                         prompt_tokens,
                                                         self._token_tracker,
                                                         self._context,
                                                         prompt=prompt,
                                                         model=model,
                                                         **kwargs)

                    response = await func(client_self,
                                          model=model,
                                          prompt=prompt,
                                          **kwargs)
                    completion = response.get('response', '')
                    completion_tokens = count_text_tokens(completion, model)

                    span.set_attributes({
                        "completion.tokens": completion_tokens,
                        "total.tokens": prompt_tokens + completion_tokens,
                        "model": model
                    })

                    self._token_tracker.update(
                        "ollama",
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens)

                    if self._context and self._context.policy_engine:
                        enforce_policies(self._context,
                                         span,
                                         response,
                                         prompt=prompt,
                                         completion=completion)

                    return response

                except Exception as e:
                    span.record_exception(e)
                    raise

        return wrapper

    def _wrap_async_chat(self, func: Any) -> Any:
        """Wrap async chat with tracing and token tracking."""

        @wraps(func)
        async def wrapper(client_self: Any,
                          model: str = '',
                          messages: list = None,
                          **kwargs: Any) -> Any:
            with start_llm_span("ollama.chat.async", kwargs) as span:
                self.logger.info("Starting async chat request",
                                 extra={"model": model})
                try:
                    prompt = messages[-1].get('content',
                                              '') if messages else ''
                    prompt_tokens = sum(
                        count_text_tokens(msg.get('content', ''), model)
                        for msg in messages or [])
                    span.set_attribute("prompt.tokens", prompt_tokens)

                    if kwargs.get('stream', False):
                        return await handle_async_stream(func,
                                                         client_self,
                                                         span,
                                                         prompt_tokens,
                                                         self._token_tracker,
                                                         self._context,
                                                         prompt=prompt,
                                                         model=model,
                                                         **kwargs)

                    response = await func(client_self,
                                          model=model,
                                          messages=messages,
                                          **kwargs)
                    completion = response.get('message', {}).get('content', '')
                    completion_tokens = count_text_tokens(completion, model)

                    span.set_attributes({
                        "completion.tokens": completion_tokens,
                        "total.tokens": prompt_tokens + completion_tokens,
                        "model": model
                    })

                    self._token_tracker.update(
                        "ollama",
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens)

                    if self._context and self._context.policy_engine:
                        enforce_policies(self._context,
                                         span,
                                         response,
                                         prompt=prompt,
                                         completion=completion)

                    return response

                except Exception as e:
                    span.record_exception(e)
                    raise

        return wrapper

    def _wrap_embed(self, func: Any) -> Any:
        """Wrap sync embed with tracing."""

        @wraps(func)
        def wrapper(client_self: Any,
                    model: str = '',
                    input: str = '',
                    **kwargs: Any) -> Any:
            with start_llm_span("ollama.embed", kwargs) as span:
                try:
                    input_tokens = count_text_tokens(input, model)
                    span.set_attribute("prompt.tokens", input_tokens)

                    response = func(client_self,
                                    model=model,
                                    input=input,
                                    **kwargs)
                    span.set_attributes({
                        "embedding_dim":
                        len(response.get('embeddings', [[]])[0]),
                        "model":
                        model
                    })

                    self._token_tracker.update("ollama",
                                               prompt_tokens=input_tokens,
                                               completion_tokens=0)

                    return response

                except Exception as e:
                    span.record_exception(e)
                    raise

        return wrapper

    def _wrap_async_embed(self, func: Any) -> Any:
        """Wrap async embed with tracing."""

        @wraps(func)
        async def wrapper(client_self: Any,
                          model: str = '',
                          input: str = '',
                          **kwargs: Any) -> Any:
            with start_llm_span("ollama.embed.async", kwargs) as span:
                try:
                    input_tokens = count_text_tokens(input, model)
                    span.set_attribute("prompt.tokens", input_tokens)

                    response = await func(client_self,
                                          model=model,
                                          input=input,
                                          **kwargs)
                    span.set_attributes({
                        "embedding_dim":
                        len(response.get('embeddings', [[]])[0]),
                        "model":
                        model
                    })

                    self._token_tracker.update("ollama",
                                               prompt_tokens=input_tokens,
                                               completion_tokens=0)

                    return response

                except Exception as e:
                    span.record_exception(e)
                    raise

        return wrapper

    def __enter__(self) -> 'OllamaPatcher':
        """Enable use as a context manager."""
        self.patch()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Cleanup when exiting context."""
        self.unpatch()
