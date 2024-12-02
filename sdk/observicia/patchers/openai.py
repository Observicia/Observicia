import functools
import os
from typing import Any, Dict, Optional, Union, AsyncGenerator

from openai import AsyncOpenAI, OpenAI
from openai.resources.chat.completions import AsyncCompletions as AsyncChatCompletions
from openai.resources.chat.completions import Completions as ChatCompletions
from openai.resources.completions import Completions, AsyncCompletions
from openai.resources.embeddings import AsyncEmbeddings, Embeddings
from openai.resources.files import AsyncFiles, Files
from openai.resources.images import AsyncImages, Images
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from ..core.token_tracker import TokenTracker
from ..core.context_manager import ObservabilityContext
from ..utils.tracing_helpers import start_llm_span, record_token_usage
from ..utils.token_helpers import count_prompt_tokens, count_text_tokens, update_token_usage
from ..utils.policy_helpers import enforce_policies
from ..utils.stream_helpers import handle_async_stream, handle_stream
from ..utils.logging import ObserviciaLogger


class OpenAIPatcher:
    """Enhanced patcher for OpenAI's v1.0+ API with observability features."""

    def __init__(self,
                 token_tracker: Optional[TokenTracker] = None,
                 log_file: Optional[str] = None,
                 context: Optional[ObservabilityContext] = None):
        self._original_functions: Dict[str, Any] = {}
        self._token_tracker = token_tracker or TokenTracker()
        self._context = context or ObservabilityContext.get_current()
        self.logger = ObserviciaLogger("OpenAIPatcher",
                                       console_output=False,
                                       file_output=log_file,
                                       otlp_endpoint=None)

    def patch(self) -> Dict[str, Any]:
        """Apply patches to OpenAI SDK functions."""
        try:
            original_functions = {}

            # Patch completions
            if hasattr(AsyncCompletions, "create"):
                original_functions[
                    "async_completions.create"] = AsyncCompletions.create
                AsyncCompletions.create = self._wrap_async_completion(
                    AsyncCompletions.create)

            if hasattr(Completions, "create"):
                original_functions["completions.create"] = Completions.create
                Completions.create = self._wrap_completion(Completions.create)

            # Patch chat completions
            if hasattr(AsyncChatCompletions, "create"):
                original_functions[
                    "async_chat_completions.create"] = AsyncChatCompletions.create
                AsyncChatCompletions.create = self._wrap_async_chat_completion(
                    AsyncChatCompletions.create)

            if hasattr(ChatCompletions, "create"):
                original_functions[
                    "chat_completions.create"] = ChatCompletions.create
                ChatCompletions.create = self._wrap_chat_completion(
                    ChatCompletions.create)

            # Patch embeddings
            if hasattr(AsyncEmbeddings, "create"):
                original_functions[
                    "async_embeddings.create"] = AsyncEmbeddings.create
                AsyncEmbeddings.create = self._wrap_async_embedding(
                    AsyncEmbeddings.create)

            if hasattr(Embeddings, "create"):
                original_functions["embeddings.create"] = Embeddings.create
                Embeddings.create = self._wrap_embedding(Embeddings.create)

            # Patch files
            if hasattr(AsyncFiles, "create"):
                original_functions["async_files.create"] = AsyncFiles.create
                AsyncFiles.create = self._wrap_async_file_upload(
                    AsyncFiles.create)

            if hasattr(Files, "create"):
                original_functions["files.create"] = Files.create
                Files.create = self._wrap_file_upload(Files.create)

            # Patch images
            if hasattr(AsyncImages, "generate"):
                original_functions[
                    "async_images.generate"] = AsyncImages.generate
                AsyncImages.generate = self._wrap_async_image_generation(
                    AsyncImages.generate)

            if hasattr(Images, "generate"):
                original_functions["images.generate"] = Images.generate
                Images.generate = self._wrap_image_generation(Images.generate)

            self._original_functions = original_functions
            return original_functions

        except ImportError as e:
            raise ImportError(f"OpenAI SDK not installed: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error patching OpenAI SDK: {str(e)}")

    def unpatch(self, original_functions: Dict[str, Any]) -> None:
        """Restore original OpenAI SDK functions."""
        try:
            for func_path, original_func in original_functions.items():
                module_path, func_name = func_path.split('.')
                if hasattr(globals().get(module_path), func_name):
                    setattr(globals()[module_path], func_name, original_func)
        except Exception as e:
            raise RuntimeError(f"Error unpatching OpenAI SDK: {str(e)}")

    def _wrap_chat_completion(self, func: Any) -> Any:
        """Wrap sync chat completion with tracing and token tracking."""

        @functools.wraps(func)
        def wrapper(client_self: ChatCompletions, *args: Any,
                    **kwargs: Any) -> Any:
            with start_llm_span("openai.chat.completion", kwargs) as span:
                self.logger.info("Starting chat completion request",
                                 extra={"model": kwargs.get('model')})
                try:
                    messages = kwargs.get('messages', [])
                    model = kwargs.get('model', 'gpt-3.5-turbo')
                    prompt_tokens = count_prompt_tokens(messages, model)
                    span.set_attribute("prompt.tokens", prompt_tokens)
                    prompt = messages[-1]['content'] if messages else ""

                    if kwargs.get('stream', False):
                        return handle_stream(func,
                                             client_self,
                                             span,
                                             prompt_tokens,
                                             self._token_tracker,
                                             self._context,
                                             prompt=prompt,
                                             is_chat=True,
                                             *args,
                                             **kwargs)

                    response = func(client_self, *args, **kwargs)
                    total_tokens = response.usage.total_tokens if hasattr(
                        response, 'usage') else 0
                    completion_tokens = response.usage.completion_tokens if hasattr(
                        response, 'usage') else 0

                    span.set_attribute("completion.tokens", completion_tokens)
                    span.set_attribute("total.tokens", total_tokens)

                    if hasattr(response, 'usage'):
                        update_token_usage(self._token_tracker, "openai",
                                           response.usage)

                    completion = response.choices[
                        0].message.content if response.choices else ""
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

    def _wrap_async_chat_completion(self, func: Any) -> Any:
        """Wrap async chat completion with tracing and token tracking."""

        @functools.wraps(func)
        async def wrapper(client_self: AsyncChatCompletions, *args: Any,
                          **kwargs: Any) -> Any:
            with start_llm_span("openai.chat.completion.async",
                                kwargs) as span:
                self.logger.info("Starting async chat completion request",
                                 extra={"model": kwargs.get('model')})
                try:
                    messages = kwargs.get('messages', [])
                    model = kwargs.get('model', 'gpt-3.5-turbo')
                    prompt_tokens = count_prompt_tokens(messages, model)
                    span.set_attribute("prompt.tokens", prompt_tokens)
                    prompt = messages[-1]['content'] if messages else ""

                    if kwargs.get('stream', False):
                        return await handle_async_stream(func,
                                                         client_self,
                                                         span,
                                                         prompt_tokens,
                                                         self._token_tracker,
                                                         self._context,
                                                         prompt=prompt,
                                                         is_chat=True,
                                                         *args,
                                                         **kwargs)

                    response = await func(client_self, *args, **kwargs)
                    total_tokens = response.usage.total_tokens if hasattr(
                        response, 'usage') else 0
                    completion_tokens = response.usage.completion_tokens if hasattr(
                        response, 'usage') else 0

                    span.set_attribute("completion.tokens", completion_tokens)
                    span.set_attribute("total.tokens", total_tokens)

                    if hasattr(response, 'usage'):
                        update_token_usage(self._token_tracker, "openai",
                                           response.usage)

                    completion = response.choices[
                        0].message.content if response.choices else ""

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

    def _wrap_completion(self, func: Any) -> Any:
        """Wrap sync completion with tracing and token tracking."""

        @functools.wraps(func)
        def wrapper(client_self: Completions, *args: Any,
                    **kwargs: Any) -> Any:
            with start_llm_span("openai.completion", kwargs) as span:
                self.logger.info("Starting completion request",
                                 extra={"model": kwargs.get('model')})
                try:
                    prompt = kwargs.get('prompt', '')
                    model = kwargs.get('model', 'gpt-3.5-turbo')
                    prompt_tokens = count_text_tokens(prompt, model) if isinstance(prompt, str) else \
                                  sum(count_text_tokens(p, model) for p in prompt)

                    span.set_attribute("prompt.tokens", prompt_tokens)

                    if kwargs.get('stream', False):
                        return handle_stream(func,
                                             client_self,
                                             span,
                                             prompt_tokens,
                                             self._token_tracker,
                                             self._context,
                                             prompt=prompt,
                                             is_chat=False,
                                             *args,
                                             **kwargs)

                    response = func(client_self, *args, **kwargs)
                    total_tokens = response.usage.total_tokens if hasattr(
                        response, 'usage') else 0
                    completion_tokens = response.usage.completion_tokens if hasattr(
                        response, 'usage') else 0

                    span.set_attribute("completion.tokens", completion_tokens)
                    span.set_attribute("total.tokens", total_tokens)

                    if hasattr(response, 'usage'):
                        update_token_usage(self._token_tracker, "openai",
                                           response.usage)

                    completion = response.choices[
                        0].text if response.choices else ""
                    enforce_policies(
                        self._context,
                        span,
                        response,
                        prompt=prompt if isinstance(prompt, str) else
                        prompt[0],  # Use first prompt if multiple
                        completion=completion)
                    return response

                except Exception as e:
                    span.record_exception(e)
                    raise

        return wrapper

    def _wrap_async_completion(self, func: Any) -> Any:
        """Wrap async completion with tracing and token tracking."""

        @functools.wraps(func)
        async def wrapper(client_self: AsyncCompletions, *args: Any,
                          **kwargs: Any) -> Any:
            with start_llm_span("openai.completion.async", kwargs) as span:
                self.logger.info("Starting async completion request",
                                 extra={"model": kwargs.get('model')})
                try:
                    prompt = kwargs.get('prompt', '')
                    model = kwargs.get('model', 'gpt-3.5-turbo')
                    prompt_tokens = count_text_tokens(prompt, model) if isinstance(prompt, str) else \
                                  sum(count_text_tokens(p, model) for p in prompt)

                    span.set_attribute("prompt.tokens", prompt_tokens)

                    if kwargs.get('stream', False):
                        return await handle_async_stream(func,
                                                         client_self,
                                                         span,
                                                         prompt_tokens,
                                                         self._token_tracker,
                                                         self._context,
                                                         is_chat=False,
                                                         *args,
                                                         **kwargs)

                    response = await func(client_self, *args, **kwargs)
                    total_tokens = response.usage.total_tokens if hasattr(
                        response, 'usage') else 0
                    completion_tokens = response.usage.completion_tokens if hasattr(
                        response, 'usage') else 0

                    span.set_attribute("completion.tokens", completion_tokens)
                    span.set_attribute("total.tokens", total_tokens)

                    if hasattr(response, 'usage'):
                        update_token_usage(self._token_tracker, "openai",
                                           response.usage)

                    completion = response.choices[
                        0].text if response.choices else ""
                    enforce_policies(
                        self._context,
                        span,
                        response,
                        prompt=prompt if isinstance(prompt, str) else
                        prompt[0],  # Use first prompt if multiple
                        completion=completion)
                    return response

                except Exception as e:
                    span.record_exception(e)
                    raise

        return wrapper

    def _wrap_embedding(self, func: Any) -> Any:
        """Wrap sync embedding with tracing and token tracking."""

        @functools.wraps(func)
        def wrapper(client_self: Embeddings, *args: Any, **kwargs: Any) -> Any:
            with start_llm_span("openai.embeddings", kwargs) as span:
                try:
                    input_text = kwargs.get('input', '')
                    model = kwargs.get('model', 'text-embedding-ada-002')
                    input_tokens = count_text_tokens(input_text, model) if isinstance(input_text, str) else \
                                 sum(count_text_tokens(text, model) for text in input_text)

                    span.set_attribute("input.tokens", input_tokens)
                    response = func(client_self, *args, **kwargs)

                    total_tokens = response.usage.total_tokens if hasattr(
                        response, 'usage') else input_tokens
                    span.set_attribute("total.tokens", total_tokens)

                    if hasattr(response, 'usage'):
                        update_token_usage(self._token_tracker, "openai",
                                           response.usage)
                    return response

                except Exception as e:
                    span.record_exception(e)
                    raise

        return wrapper

    def _wrap_async_embedding(self, func: Any) -> Any:
        """Wrap async embedding with tracing and token tracking."""

        @functools.wraps(func)
        async def wrapper(client_self: AsyncEmbeddings, *args: Any,
                          **kwargs: Any) -> Any:
            with start_llm_span("openai.embeddings.async", kwargs) as span:
                try:
                    input_text = kwargs.get('input', '')
                    model = kwargs.get('model', 'text-embedding-ada-002')
                    input_tokens = count_text_tokens(input_text, model) if isinstance(input_text, str) else \
                                 sum(count_text_tokens(text, model) for text in input_text)

                    span.set_attribute("input.tokens", input_tokens)
                    response = await func(client_self, *args, **kwargs)

                    total_tokens = response.usage.total_tokens if hasattr(
                        response, 'usage') else input_tokens
                    span.set_attribute("total.tokens", total_tokens)

                    if hasattr(response, 'usage'):
                        update_token_usage(self._token_tracker, "openai",
                                           response.usage)
                    return response

                except Exception as e:
                    span.record_exception(e)
                    raise

        return wrapper

    def _wrap_file_upload(self, func: Any) -> Any:
        """Wrap sync file upload with tracing."""

        @functools.wraps(func)
        def wrapper(client_self: Files, *args: Any, **kwargs: Any) -> Any:
            with start_llm_span("openai.files.upload", kwargs) as span:
                try:
                    file = kwargs.get('file')
                    if hasattr(file, 'seek') and hasattr(file, 'tell'):
                        current_pos = file.tell()
                        file.seek(0, os.SEEK_END)
                        file_size = file.tell()
                        file.seek(current_pos)
                        span.set_attribute("file.size_bytes", file_size)

                    return func(client_self, *args, **kwargs)

                except Exception as e:
                    span.record_exception(e)
                    raise

        return wrapper

    def _wrap_async_file_upload(self, func: Any) -> Any:
        """Wrap async file upload with tracing."""

        @functools.wraps(func)
        async def wrapper(client_self: AsyncFiles, *args: Any,
                          **kwargs: Any) -> Any:
            with start_llm_span("openai.files.upload.async", kwargs) as span:
                try:
                    file = kwargs.get('file')
                    if hasattr(file, 'seek') and hasattr(file, 'tell'):
                        current_pos = file.tell()
                        file.seek(0, os.SEEK_END)
                        file_size = file.tell()
                        file.seek(current_pos)
                        span.set_attribute("file.size_bytes", file_size)

                    return await func(client_self, *args, **kwargs)

                except Exception as e:
                    span.record_exception(e)
                    raise

        return wrapper

    def _wrap_image_generation(self, func: Any) -> Any:
        """Wrap sync image generation with tracing."""

        @functools.wraps(func)
        def wrapper(client_self: Images, *args: Any, **kwargs: Any) -> Any:
            with start_llm_span("openai.images.generate", kwargs) as span:
                try:
                    prompt = kwargs.get('prompt', '')
                    prompt_tokens = count_text_tokens(prompt, "gpt-3.5-turbo")

                    span.set_attributes({
                        "prompt.tokens":
                        prompt_tokens,
                        "image.size":
                        kwargs.get('size', 'unknown'),
                        "image.quality":
                        kwargs.get('quality', 'standard'),
                        "image.style":
                        kwargs.get('style', 'natural')
                    })

                    response = func(client_self, *args, **kwargs)
                    span.set_attribute(
                        "images.generated",
                        len(response.data) if hasattr(response, 'data') else 0)
                    return response

                except Exception as e:
                    span.record_exception(e)
                    raise

        return wrapper

    def _wrap_async_image_generation(self, func: Any) -> Any:
        """Wrap async image generation with tracing."""

        @functools.wraps(func)
        async def wrapper(client_self: AsyncImages, *args: Any,
                          **kwargs: Any) -> Any:
            with start_llm_span("openai.images.generate.async",
                                kwargs) as span:
                try:
                    prompt = kwargs.get('prompt', '')
                    prompt_tokens = count_text_tokens(prompt, "gpt-3.5-turbo")

                    span.set_attributes({
                        "prompt.tokens":
                        prompt_tokens,
                        "image.size":
                        kwargs.get('size', 'unknown'),
                        "image.quality":
                        kwargs.get('quality', 'standard'),
                        "image.style":
                        kwargs.get('style', 'natural')
                    })

                    response = await func(client_self, *args, **kwargs)
                    span.set_attribute(
                        "images.generated",
                        len(response.data) if hasattr(response, 'data') else 0)
                    return response

                except Exception as e:
                    span.record_exception(e)
                    raise

        return wrapper

    def __enter__(self) -> 'OpenAIPatcher':
        """Enable use as a context manager."""
        self.patch()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Cleanup when exiting context."""
        if self._original_functions:
            self.unpatch(self._original_functions)
