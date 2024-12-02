"""Utility functions for handling streaming responses"""

from typing import Any, AsyncGenerator, Generator
from opentelemetry import trace
from opentelemetry.trace import Span, get_tracer, SpanKind, Status, StatusCode

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


"""
The span is created for the entire streaming operation, and child spans are created for each chunk of the response.
Th following is a sequence diagram of the streaming operation:
sequenceDiagram
    participant Root
    participant Chat as openai.chat.completion.async<br/>span_id: 0xd0dc346c
    participant Stream as stream_processing<br/>span_id: 0x137d604c
    participant Chunk1 as process_chunk (1/9)<br/>span_id: 0xb6fa18be
    participant Chunk2 as process_chunk (2/9)<br/>span_id: 0xd807061c
    participant ChunkN as process_chunk (3-9)
    participant Final as finalize_stream<br/>span_id: 0x472739f5

    Note over Root,Final: trace_id: 0x43e1563a4cc36cb032326d5564d28cbc

    Root->>Chat: start (17:02:11.643)
    Note over Chat: attributes:<br/>service.name: chatbot-app<br/>llm.provider: openai<br/>prompt.tokens: 7

    Chat->>Stream: start (17:02:12.752)
    Note over Stream: attributes:<br/>prompt.tokens: 7<br/>streaming: true

    Stream->>Chunk1: start (17:02:12.786)
    Note over Chunk1: attribute:<br/>stream.chunks_received: 1

    Stream->>Chunk2: start (17:02:12.786)
    Note over Chunk2: attribute:<br/>stream.chunks_received: 2

    Stream->>ChunkN: start (multiple chunks)
    Note over ChunkN: chunks 3-9<br/>timestamps: 17:02:12.798-832

    Stream->>Final: start (17:02:12.839)
    Note over Final: attributes:<br/>completion.tokens: 9<br/>total.tokens: 16<br/>stream.total_chunks: 9

    Final-->>Stream: end (17:02:12.840)
    ChunkN-->>Stream: end
    Chunk2-->>Stream: end
    Chunk1-->>Stream: end
    Stream-->>Chat: end (17:02:12.752)
    Chat-->>Root: end (17:02:12.752)
"""


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

    # Create parent context for streaming operation
    parent_ctx = trace.set_span_in_context(parent_span)

    # Create a new span for the entire streaming operation as child of parent span
    with tracer.start_span("stream_processing",
                           context=parent_ctx,
                           kind=SpanKind.INTERNAL) as stream_span:
        stream_span.set_attribute("prompt.tokens", prompt_tokens)
        stream_span.set_attribute("streaming", True)

        # Create context for child spans
        stream_ctx = trace.set_span_in_context(stream_span)

        async def wrapped_generator():
            nonlocal chunk_count

            try:
                async for chunk in response_generator:
                    content = _extract_content_from_chunk(chunk, is_chat)
                    if content:
                        accumulated_response.append(content)
                        chunk_count += 1
                        # Create chunk span as child of stream span
                        with tracer.start_span(
                                "process_chunk",
                                context=stream_ctx,
                                kind=SpanKind.INTERNAL) as chunk_span:
                            chunk_span.set_attribute("stream.chunks_received",
                                                     chunk_count)
                    yield chunk

                # After stream completes, process accumulated response
                with tracer.start_span("finalize_stream",
                                       context=stream_ctx,
                                       kind=SpanKind.INTERNAL) as final_span:
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

                    enforce_policies(context, final_span, response_content)

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
