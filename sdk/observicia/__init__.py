"""
Observicia - Policy-Aware Tracing SDK for LLM Applications
"""

from observicia.core.context_manager import ObservabilityContext
from observicia.core.policy_engine import PolicyEngine, PolicyResult
from observicia.core.tracing_manager import TracingClient
from observicia.core.token_tracker import TokenTracker
from observicia.core.patch_manager import PatchManager
from observicia.core.policy_engine import Policy
from typing import List, Optional

__version__ = "0.1.0"


def init(service_name: str,
         otel_endpoint: str = None,
         opa_endpoint: str = None,
         trace_console: bool = False,
         log_file: Optional[str] = None,
         policies: Optional[List[Policy]] = None) -> None:
    """Initialize the Observicia SDK.
    
    Args:
        service_name: Name of the service using the SDK
        otel_endpoint: OpenTelemetry endpoint for tracing
        opa_endpoint: OPA server endpoint for policy evaluation
        trace_console: If True, prints traces to console for debugging
        policies: List of Policy objects defining available policies
    """
    ObservabilityContext.initialize(service_name=service_name,
                                    otel_endpoint=otel_endpoint,
                                    opa_endpoint=opa_endpoint,
                                    trace_console=trace_console,
                                    log_file=log_file,
                                    policies=policies)

    # Auto-detect and patch installed providers
    patch_manager = PatchManager()
    patch_manager.patch_all()


# Expose main decorators
from observicia.core.tracing_manager import trace, trace_rag, trace_stream

# Expose utilities
from observicia.utils.helpers import get_current_span, get_current_context

__all__ = [
    "init", "trace", "trace_rag", "trace_stream", "get_current_span",
    "get_current_context", "PolicyResult", "__version__"
]
