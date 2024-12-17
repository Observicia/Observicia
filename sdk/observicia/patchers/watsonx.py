import functools
import logging
from typing import Any, Dict, Optional, Generator, Union, Literal

from ibm_watsonx_ai.foundation_models import ModelInference
from ibm_watsonx_ai.foundation_models.schema import TextGenParameters, TextChatParameters

from ..core.token_tracker import TokenTracker
from ..core.context_manager import ObservabilityContext
from ..utils.tracing_helpers import start_llm_span, record_token_usage
from ..utils.token_helpers import count_prompt_tokens, count_text_tokens, update_token_usage
from ..utils.logging import ObserviciaLogger


class WatsonxPatcher:
    """IBM watsonx.ai Foundation Models."""

    def __init__(self,
                 token_tracker: Optional[TokenTracker] = None,
                 log_file: Optional[str] = None,
                 context: Optional[ObservabilityContext] = None):
        self._original_functions: Dict[str, Any] = {}
        self._token_tracker = token_tracker or TokenTracker()
        self._context = context or ObservabilityContext.get_current()
        self._patched = False
        self._logger = self._context._logger if hasattr(
            self._context, '_logger') else logging.getLogger(__name__)

    def _wrap_generate(self, func: Any) -> Any:
        """Wrap generate with tracing and token tracking."""
        logger = self._logger
        token_tracker = self._token_tracker

        @functools.wraps(func)
        def wrapper(
            model_self: ModelInference,
            prompt: Union[str, list, None] = None,
            params: Optional[Union[dict, TextGenParameters]] = None,
            guardrails: bool = False,
            guardrails_hap_params: Optional[dict] = None,
            guardrails_pii_params: Optional[dict] = None,
            concurrency_limit: int = 10,
            async_mode: bool = False,
            validate_prompt_variables: bool = True,
        ) -> Union[dict, list[dict], Generator]:
            with start_llm_span("watsonx.generate", {
                    "model": model_self.model_id,
                    "provider": "watsonx-ai"
            }) as span:
                logger.info("Starting text generation request",
                            extra={"model": model_self.model_id})
                try:
                    if isinstance(prompt, str):
                        span.set_attribute("prompt", prompt)

                    response = func(model_self, prompt, params, guardrails,
                                    guardrails_hap_params,
                                    guardrails_pii_params, concurrency_limit,
                                    async_mode, validate_prompt_variables)

                    # Extract and record token usage from response
                    if isinstance(response, dict) and "results" in response:
                        input_token_count = response.get(
                            "input_token_count", 0)
                        generated_token_count = len(response["results"][0].get(
                            "generated_text", "").split())

                        span.set_attribute("prompt.tokens", input_token_count)
                        span.set_attribute("completion.tokens",
                                           generated_token_count)
                        span.set_attribute(
                            "total.tokens",
                            input_token_count + generated_token_count)

                        if token_tracker:
                            token_tracker.add_usage(
                                "watsonx", {
                                    "prompt_tokens":
                                    input_token_count,
                                    "completion_tokens":
                                    generated_token_count,
                                    "total_tokens":
                                    input_token_count + generated_token_count
                                })

                    return response

                except Exception as e:
                    span.record_exception(e)
                    raise

        return wrapper

    def _wrap_generate_text(self, func: Any) -> Any:
        """Wrap generate_text with tracing and token tracking."""
        logger = self._logger
        token_tracker = self._token_tracker

        @functools.wraps(func)
        def wrapper(
            model_self: ModelInference,
            prompt: Union[str, list, None] = None,
            params: Optional[Union[dict, TextGenParameters]] = None,
            raw_response: bool = False,
            guardrails: bool = False,
            guardrails_hap_params: Optional[dict] = None,
            guardrails_pii_params: Optional[dict] = None,
            concurrency_limit: int = 10,
            validate_prompt_variables: bool = True,
        ) -> Union[str, list, dict]:
            with start_llm_span("watsonx.generate_text", {
                    "model": model_self.model_id,
                    "provider": "watsonx-ai"
            }) as span:
                logger.info("Starting text generation request",
                            extra={"model": model_self.model_id})
                try:
                    if isinstance(prompt, str):
                        span.set_attribute("prompt", prompt)

                    response = func(model_self, prompt, params, raw_response,
                                    guardrails, guardrails_hap_params,
                                    guardrails_pii_params, concurrency_limit,
                                    validate_prompt_variables)

                    # Handle token tracking if raw_response is True
                    if raw_response and isinstance(
                            response, dict) and "results" in response:
                        input_token_count = response.get(
                            "input_token_count", 0)
                        generated_token_count = len(response["results"][0].get(
                            "generated_text", "").split())

                        span.set_attribute("prompt.tokens", input_token_count)
                        span.set_attribute("completion.tokens",
                                           generated_token_count)
                        span.set_attribute(
                            "total.tokens",
                            input_token_count + generated_token_count)

                        if token_tracker:
                            update_token_usage(
                                self._token_tracker, "watsonx", {
                                    "prompt_tokens":
                                    input_token_count,
                                    "completion_tokens":
                                    generated_token_count,
                                    "total_tokens":
                                    input_token_count + generated_token_count
                                })

                    return response

                except Exception as e:
                    span.record_exception(e)
                    raise

        return wrapper

    def _wrap_chat(self, func: Any) -> Any:
        """Wrap chat with tracing and token tracking."""
        logger = self._logger
        token_tracker = self._token_tracker

        @functools.wraps(func)
        def wrapper(
            model_self: ModelInference,
            messages: list[dict],
            params: Optional[Union[dict, TextChatParameters]] = None,
            tools: Optional[list] = None,
            tool_choice: Optional[dict] = None,
            tool_choice_option: Optional[Literal["none", "auto"]] = None,
        ) -> dict:
            with start_llm_span("watsonx.chat", {
                    "model": model_self.model_id,
                    "provider": "watsonx-ai"
            }) as span:
                logger.info("Starting chat request",
                            extra={"model": model_self.model_id})
                try:
                    span.set_attribute("messages", str(messages))

                    response = func(model_self, messages, params, tools,
                                    tool_choice, tool_choice_option)

                    # Extract and record token usage
                    if "choices" in response:
                        message_tokens = sum(
                            len(m.get("content", "").split())
                            for m in messages)
                        completion_tokens = len(
                            response["choices"][0]["message"].get(
                                "content", "").split())

                        span.set_attribute("prompt.tokens", message_tokens)
                        span.set_attribute("completion.tokens",
                                           completion_tokens)
                        span.set_attribute("total.tokens",
                                           message_tokens + completion_tokens)

                        if token_tracker:
                            update_token_usage(
                                self._token_tracker, "watsonx", {
                                    "prompt_tokens":
                                    message_tokens,
                                    "completion_tokens":
                                    completion_tokens,
                                    "total_tokens":
                                    message_tokens + completion_tokens
                                })

                    return response

                except Exception as e:
                    span.record_exception(e)
                    raise

        return wrapper

    def patch(self) -> Dict[str, Any]:
        """Apply patches to watsonx.ai SDK functions."""
        if self._patched:
            return self._original_functions

        try:
            original_functions = {
                'generate': ModelInference.generate,
                'generate_text': ModelInference.generate_text,
                'chat': ModelInference.chat,
            }

            # Patch methods
            ModelInference.generate = self._wrap_generate(
                ModelInference.generate)
            ModelInference.generate_text = self._wrap_generate_text(
                ModelInference.generate_text)
            ModelInference.chat = self._wrap_chat(ModelInference.chat)

            self._original_functions = original_functions
            self._patched = True
            return original_functions

        except ImportError as e:
            raise ImportError(f"watsonx.ai SDK not installed: {str(e)}")
        except Exception as e:
            self._rollback_patches()
            raise RuntimeError(f"Error patching watsonx.ai SDK: {str(e)}")

    def unpatch(self,
                original_functions: Optional[Dict[str, Any]] = None) -> None:
        """Restore original watsonx.ai SDK functions."""
        if not self._patched:
            return

        try:
            original_functions = original_functions or self._original_functions
            for func_name, original_func in original_functions.items():
                setattr(ModelInference, func_name, original_func)

            self._patched = False
            self._original_functions = {}

        except Exception as e:
            raise RuntimeError(f"Error unpatching watsonx.ai SDK: {str(e)}")

    def _rollback_patches(self) -> None:
        """Rollback patches if patching fails."""
        self.unpatch()

    def __enter__(self) -> 'WatsonxPatcher':
        """Enable use as a context manager."""
        self.patch()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Cleanup when exiting context."""
        self.unpatch(self._original_functions)
