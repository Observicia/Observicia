"""Utility functions for handling streaming responses"""

from typing import Any, AsyncGenerator, Generator
from opentelemetry.trace import Span, get_tracer
from .token_helpers import count_text_tokens
from .policy_helpers import enforce_policies


def _extract_content_from_chunk(chunk: Any, is_chat: bool = False) -> str:
    """Extract content from a response chunk based on type."""
    if not chunk.choices or not chunk.choices[0]:
        return ""

    if is_chat:
        # Chat completion format
        delta = getattr(chunk.choices[0], 'delta', None)
        if delta:
            return delta.content or ""
    else:
        # Regular completion format
        return chunk.choices[0].text or ""

    return ""


async def handle_async_stream(func: Any,
                              client: Any,
                              parent_span: Span,
                              prompt_tokens: int,
                              token_tracker: Any,
                              context: Any,
                              is_chat: bool = False,
                              *args: Any,
                              **kwargs: Any) -> AsyncGenerator:
    """Handle async streaming responses."""
    tracer = get_tracer(__name__)
    accumulated_response = []
    chunk_count = 0

    # Get the generator first
    response_generator = await func(client, *args, **kwargs)

    # Create a new span for the entire streaming operation
    with tracer.start_as_current_span("stream_processing") as stream_span:
        stream_span.set_attribute("prompt.tokens", prompt_tokens)
        stream_span.set_attribute("streaming", True)

        async def wrapped_generator():
            nonlocal chunk_count

            try:
                async for chunk in response_generator:
                    content = _extract_content_from_chunk(chunk, is_chat)
                    if content:
                        accumulated_response.append(content)
                        chunk_count += 1
                        with tracer.start_as_current_span(
                                "process_chunk") as chunk_span:
                            chunk_span.set_attribute("stream.chunks_received",
                                                     chunk_count)
                    yield chunk

                # After stream completes, process accumulated response
                with tracer.start_as_current_span(
                        "finalize_stream") as final_span:
                    full_response = ''.join(accumulated_response)
                    model = kwargs.get('model', 'gpt-3.5-turbo')
                    completion_tokens = count_text_tokens(full_response, model)
                    total_tokens = prompt_tokens + completion_tokens

                    final_span.set_attribute("completion.tokens",
                                             completion_tokens)
                    final_span.set_attribute("total.tokens", total_tokens)
                    final_span.set_attribute("stream.total_chunks",
                                             chunk_count)

                    token_tracker.update("openai",
                                         prompt_tokens=prompt_tokens,
                                         completion_tokens=completion_tokens)

                    # Structure response based on type
                    response_content = {
                        'choices': [{
                            'message': {
                                'content': full_response
                            }
                        }]
                    } if is_chat else {
                        'choices': [{
                            'text': full_response
                        }]
                    }

                    await enforce_policies(context, final_span,
                                           response_content)

            except Exception as e:
                stream_span.record_exception(e)
                raise

        return wrapped_generator()


def handle_stream(func: Any,
                  client: Any,
                  parent_span: Span,
                  prompt_tokens: int,
                  token_tracker: Any,
                  context: Any,
                  is_chat: bool = False,
                  *args: Any,
                  **kwargs: Any) -> Generator:
    """Handle sync streaming responses."""
    tracer = get_tracer(__name__)
    accumulated_response = []
    chunk_count = 0

    # Get the sync generator
    response_generator = func(client, *args, **kwargs)

    # Create a new span for the entire streaming operation
    with tracer.start_as_current_span("stream_processing") as stream_span:
        stream_span.set_attribute("prompt.tokens", prompt_tokens)
        stream_span.set_attribute("streaming", True)

        try:
            for chunk in response_generator:
                content = _extract_content_from_chunk(chunk, is_chat)
                if content:
                    accumulated_response.append(content)
                    chunk_count += 1
                    with tracer.start_as_current_span(
                            "process_chunk") as chunk_span:
                        chunk_span.set_attribute("stream.chunks_received",
                                                 chunk_count)
                yield chunk

            # After stream completes, process accumulated response
            with tracer.start_as_current_span("finalize_stream") as final_span:
                full_response = ''.join(accumulated_response)
                model = kwargs.get('model', 'gpt-3.5-turbo')
                completion_tokens = count_text_tokens(full_response, model)
                total_tokens = prompt_tokens + completion_tokens

                final_span.set_attribute("completion.tokens",
                                         completion_tokens)
                final_span.set_attribute("total.tokens", total_tokens)
                final_span.set_attribute("stream.total_chunks", chunk_count)

                token_tracker.update("openai",
                                     prompt_tokens=prompt_tokens,
                                     completion_tokens=completion_tokens)

                # Structure response based on type
                response_content = {
                    'choices': [{
                        'message': {
                            'content': full_response
                        }
                    }]
                } if is_chat else {
                    'choices': [{
                        'text': full_response
                    }]
                }

                enforce_policies(context, final_span, response_content)

        except Exception as e:
            stream_span.record_exception(e)
            raise
