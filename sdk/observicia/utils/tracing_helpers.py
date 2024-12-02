"""Utility functions for OpenTelemetry tracing"""

from typing import Dict, Any
from opentelemetry import trace
from opentelemetry.trace import Span
from observicia.core.context_manager import ObservabilityContext


def start_llm_span(name: str, attributes: Dict[str, Any]) -> Span:
    """Start a new trace span with LLM attributes."""
    tracer = trace.get_tracer(__name__)
    context = ObservabilityContext.get_current()

    # Combine base attributes with LLM-specific attributes
    span_attributes = {
        "service.name": context._service_name,
        "llm.provider": "openai",
        "llm.model": attributes.get('model', 'unknown'),
        "llm.request.type": name.split('.')[-1]
    }

    user_id = context.get_user_id()
    if user_id:
        span_attributes["user.id"] = user_id

    return tracer.start_span(name=name, attributes=span_attributes)


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
