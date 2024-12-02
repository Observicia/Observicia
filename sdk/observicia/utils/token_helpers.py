# token_helpers.py
"""Utility functions for token counting and tracking"""

import tiktoken
from typing import List, Dict, Any
from opentelemetry.trace import Span
from ..core.token_tracker import TokenTracker


def count_prompt_tokens(messages: List[Dict[str, Any]], model: str) -> int:
    """Count tokens in chat messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
        num_tokens = 0
        for message in messages:
            if isinstance(message.get('content'), str):
                num_tokens += len(encoding.encode(message['content']))
            num_tokens += 4  # Format tokens per message
        num_tokens += 2  # Conversation format tokens
        return num_tokens
    except Exception:
        # Fallback to approximate count
        return sum(
            len(str(msg.get('content', '')).split()) for msg in messages)


def count_text_tokens(text: str, model: str) -> int:
    """Count tokens in plain text."""
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception:
        # Fallback to approximate count
        return len(text.split())


def record_token_usage(span: Span, response: Any) -> None:
    """Record token usage in span from response."""
    if hasattr(response, 'usage'):
        usage = response.usage
        usage_dict = {}

        # Handle different usage structures
        if hasattr(usage, 'prompt_tokens'):
            usage_dict['prompt.tokens'] = usage.prompt_tokens
        if hasattr(usage, 'completion_tokens'):
            usage_dict['completion.tokens'] = usage.completion_tokens
        elif hasattr(usage, 'total_tokens') and hasattr(
                usage, 'prompt_tokens'):
            # Some APIs only give total and prompt, derive completion
            usage_dict[
                'completion.tokens'] = usage.total_tokens - usage.prompt_tokens
        if hasattr(usage, 'total_tokens'):
            usage_dict['total.tokens'] = usage.total_tokens

        # Set all available usage metrics
        span.set_attributes(usage_dict)


def update_token_usage(token_tracker: TokenTracker, provider: str,
                       usage: Any) -> None:
    """Update token tracker with usage statistics."""
    prompt_tokens = getattr(usage, 'prompt_tokens', 0)
    completion_tokens = getattr(usage, 'completion_tokens', 0)

    # If we have total but not completion, derive it
    if hasattr(usage,
               'total_tokens') and not hasattr(usage, 'completion_tokens'):
        completion_tokens = usage.total_tokens - prompt_tokens

    token_tracker.update(provider,
                         prompt_tokens=prompt_tokens,
                         completion_tokens=completion_tokens)
