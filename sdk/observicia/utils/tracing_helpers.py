"""Utility functions for OpenTelemetry tracing"""

from typing import Dict, Any
from opentelemetry import trace
from opentelemetry.trace import Span


def start_llm_span(name: str, attributes: Dict[str, Any]) -> Span:
    """Start a new trace span with LLM attributes."""
    tracer = trace.get_tracer(__name__)
    return tracer.start_span(name=name,
                             attributes={
                                 "llm.provider": "openai",
                                 "llm.model":
                                 attributes.get('model', 'unknown'),
                                 "llm.request.type": name.split('.')[-1]
                             })


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

        # print usage_dict
        print(f"Usage dict: {usage_dict}")
