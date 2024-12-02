from functools import wraps
from typing import Any, Callable, Dict, List, Optional
import asyncio
from opentelemetry import trace
from opentelemetry.trace import SpanKind
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

from .context_manager import ObservabilityContext
from .policy_engine import PolicyEngine, PolicyResult
from .token_tracker import TokenTracker
from ..utils.tracing_helpers import start_llm_span
from ..utils.policy_helpers import enforce_policies


class TracingClient:
    """Client for handling traces with policy enforcement."""

    def __init__(self,
                 service_name: str,
                 policy_engine: Optional[PolicyEngine] = None,
                 token_tracker: Optional[TokenTracker] = None,
                 otel_endpoint: Optional[str] = None,
                 trace_console: bool = False):
        """Initialize the tracing client."""
        self.service_name = service_name
        self.policy_engine = policy_engine
        self.token_tracker = token_tracker
        self.tracer = trace.get_tracer(service_name)

        # Set up trace export
        provider = TracerProvider()
        if otel_endpoint:
            otlp_processor = BatchSpanProcessor(
                OTLPSpanExporter(endpoint=otel_endpoint))
            provider.add_span_processor(otlp_processor)
        if trace_console:
            console_processor = BatchSpanProcessor(ConsoleSpanExporter())
            provider.add_span_processor(console_processor)
        trace.set_tracer_provider(provider)

    def start_span(
        self,
        name: str,
        context: Optional[Dict[str, Any]] = None,
        kind: SpanKind = SpanKind.CLIENT,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> trace.Span:
        """Start a new span with context and attributes."""
        return start_llm_span(
            name, {
                **(attributes or {}), "service.name": self.service_name
            })


class TraceDecorator:
    """Decorator for adding tracing and policy enforcement to functions."""

    def __init__(self,
                 tracing_client: TracingClient,
                 policies: Optional[List[str]] = None,
                 trace_level: str = "normal",
                 enforce_policies: bool = True):
        self.client = tracing_client
        self.policies = policies or []
        self.trace_level = trace_level
        self.enforce_policies = enforce_policies

    def __call__(self, func: Callable) -> Callable:
        """Apply the decorator to a function."""

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            with self.client.start_span(
                    name=func.__name__,
                    context={
                        "args": args,
                        "kwargs": kwargs
                    },
                    attributes={"trace.level": self.trace_level}) as span:
                try:
                    if self.enforce_policies:
                        await enforce_policies(self.client.policy_engine, span,
                                               {
                                                   "args": args,
                                                   "kwargs": kwargs,
                                                   "phase": "input"
                                               })

                    result = await func(*args, **kwargs)

                    if self.enforce_policies:
                        await enforce_policies(self.client.policy_engine, span,
                                               {
                                                   "result": result,
                                                   "phase": "output"
                                               })

                    return result

                except Exception as e:
                    span.record_exception(e)
                    raise

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with self.client.start_span(
                    name=func.__name__,
                    context={
                        "args": args,
                        "kwargs": kwargs
                    },
                    attributes={"trace.level": self.trace_level}) as span:
                try:
                    if self.enforce_policies:
                        enforce_policies(self.client.policy_engine, span, {
                            "args": args,
                            "kwargs": kwargs,
                            "phase": "input"
                        })

                    result = func(*args, **kwargs)

                    if self.enforce_policies:
                        enforce_policies(self.client.policy_engine, span, {
                            "result": result,
                            "phase": "output"
                        })

                    return result

                except Exception as e:
                    span.record_exception(e)
                    raise

        return async_wrapper if asyncio.iscoroutinefunction(
            func) else sync_wrapper


# Convenience decorators
def trace(policies: Optional[List[str]] = None,
          trace_level: str = "normal",
          enforce_policies: bool = True):
    """Decorator for basic tracing and policy enforcement."""
    context = ObservabilityContext.get_current()
    return TraceDecorator(context.tracing_client,
                          policies=policies,
                          trace_level=trace_level,
                          enforce_policies=enforce_policies)


def trace_rag(policies: Optional[List[str]] = None,
              trace_level: str = "detailed"):
    """Decorator specifically for RAG applications."""
    context = ObservabilityContext.get_current()
    return TraceDecorator(context.tracing_client,
                          policies=policies
                          or ["retrieval_relevance", "context_usage"],
                          trace_level=trace_level)


def trace_stream(policies: Optional[List[str]] = None,
                 trace_level: str = "normal"):
    """Decorator for streaming responses."""
    context = ObservabilityContext.get_current()
    return TraceDecorator(context.tracing_client,
                          policies=policies,
                          trace_level=trace_level)
