"""Utility functions for policy enforcement"""
from typing import Any, Optional
from opentelemetry.trace import Span
from observicia.core.context_manager import ObservabilityContext
from .serialization_helpers import serialize_llm_response


def enforce_policies(context: Optional[ObservabilityContext],
                     span: Span,
                     response: Any,
                     prompt: Optional[str] = None,
                     completion: Optional[str] = None) -> None:
    """Synchronously enforce policies on response."""
    if not context or not context.policy_engine:
        return

    user_id = context.get_user_id()
    if hasattr(context, '_logger'):
        metadata = {
            "model": span.attributes.get("llm.model", "unknown"),
            "provider": span.attributes.get("llm.provider", "unknown"),
            "request_type": span.attributes.get("llm.request.type", "unknown")
        }

        if prompt:
            context._logger.log_chat_interaction(interaction_type='prompt',
                                                 content=prompt,
                                                 metadata=metadata)

        if completion:
            context._logger.log_chat_interaction(interaction_type='completion',
                                                 content=completion,
                                                 metadata=metadata)

    # Serialize the response before evaluation
    serialized_response = serialize_llm_response(response)

    # Use synchronous evaluation
    result = context.policy_engine.evaluate_sync(
        {
            "response": serialized_response,
            "trace_context": {
                "trace_id": span.get_span_context().trace_id,
                "span_id": span.get_span_context().span_id,
                "attributes": dict(span.attributes)
            }
        },
        prompt=prompt,
        completion=completion)

    span.set_attributes({
        "policy.passed": result.passed,
        "policy.violations": ";".join(result.violations)
    })

    if not result.passed:
        raise ValueError(f"Policy violations: {result.violations}")
