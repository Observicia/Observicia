from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from datetime import datetime
from opentelemetry import trace, baggage
from opentelemetry.trace import Span, SpanKind
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

from .policy_engine import PolicyEngine, PolicyResult, Policy
from ..utils.logging import FileSpanExporter


@dataclass
class TraceContext:
    """Core trace context with essential fields"""
    trace_id: str
    parent_id: Optional[str]
    attributes: Dict
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    active_policies: Set[str] = field(default_factory=set)
    violation_count: int = 0
    policy_results: List[PolicyResult] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert context to dictionary for span attributes"""
        return {
            "trace_id": self.trace_id,
            "parent_id": self.parent_id or "",
            "session_id": self.session_id or "",
            "user_id": self.user_id or "",
            "active_policies": list(self.active_policies),
            "violation_count": self.violation_count,
            **self.attributes
        }

    def set_user_id(self, user_id: str) -> None:
        """Set the user ID for this context"""
        self.user_id = user_id

    def add_violation(self, policy_result: PolicyResult) -> None:
        """Record a policy violation"""
        self.violation_count += len(policy_result.violations)
        self.policy_results.append(policy_result)

    def add_policy(self, policy: str) -> None:
        """Add an active policy"""
        self.active_policies.add(policy)

    def remove_policy(self, policy: str) -> None:
        """Remove an active policy"""
        self.active_policies.discard(policy)


class ContextManager:

    def __init__(self,
                 service_name: str,
                 otel_endpoint: Optional[str] = None,
                 opa_endpoint: Optional[str] = None,
                 policies: Optional[List[Policy]] = None,
                 log_file: Optional[str] = None,
                 trace_console: bool = False):
        self._sessions: Dict[str, TraceContext] = {}
        self._service_name = service_name
        self._current_user_id: Optional[str] = None
        self._log_file = log_file

        # Initialize policy engine if OPA endpoint is provided
        self.policy_engine = PolicyEngine(
            opa_endpoint=opa_endpoint,
            policies=policies) if opa_endpoint else None

        # Set up tracing
        provider = TracerProvider()

        if otel_endpoint:
            otlp_processor = BatchSpanProcessor(
                OTLPSpanExporter(endpoint=otel_endpoint))
            provider.add_span_processor(otlp_processor)

        if trace_console:
            console_processor = BatchSpanProcessor(ConsoleSpanExporter())
            provider.add_span_processor(console_processor)

        if log_file:
            file_processor = BatchSpanProcessor(FileSpanExporter(log_file))
            provider.add_span_processor(file_processor)

        trace.set_tracer_provider(provider)
        self._tracer = trace.get_tracer(service_name)

    def get_session(self, session_id: str) -> Optional[TraceContext]:
        """Get existing session context"""
        return self._sessions.get(session_id)

    def set_user_id(self, user_id: Optional[str]) -> None:
        """Set the global user ID for all new traces"""
        self._current_user_id = user_id

    def get_user_id(self) -> Optional[str]:
        """Get the current global user ID"""
        return self._current_user_id

    async def create_span(
        self,
        name: str,
        context: Optional[TraceContext] = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[Dict] = None,
    ) -> Span:
        """Create a new span with context"""
        span = self._tracer.start_span(name=name,
                                       kind=kind,
                                       attributes={
                                           "service.name": self._service_name,
                                           **(attributes or {})
                                       })

        if context:
            span.set_attributes(context.to_dict())
            baggage.set_baggage("session_id", context.session_id or "")

        return span

    def create_session(self,
                       session_id: str,
                       initial_context: Optional[Dict] = None) -> TraceContext:
        """Create a new session context"""
        context = TraceContext(trace_id=str(session_id),
                               parent_id=None,
                               attributes=initial_context or {},
                               session_id=session_id,
                               user_id=self._current_user_id,
                               active_policies=set(self._default_policies))
        self._sessions[session_id] = context
        return context

    async def evaluate_policies(
            self,
            context: TraceContext,
            eval_context: Dict,
            policies: Optional[List[str]] = None) -> PolicyResult:
        """Evaluate policies for the given context"""
        if not self.policy_engine:
            return PolicyResult(passed=True, violations=[])

        policies = policies or list(context.active_policies)
        result = await self.policy_engine.evaluate_with_context(
            eval_context=eval_context, policies=policies)

        if not result.passed:
            context.add_violation(result)

        return result


class ObservabilityContext:
    _instance: Optional[ContextManager] = None

    @classmethod
    def initialize(cls,
                   service_name: str,
                   otel_endpoint: Optional[str] = None,
                   opa_endpoint: Optional[str] = None,
                   policies: Optional[List[Policy]] = None,
                   log_file: Optional[str] = None,
                   trace_console: bool = False) -> None:
        """Initialize the global context manager.
        
        Args:
            service_name: Name of the service using the SDK
            otel_endpoint: OpenTelemetry endpoint for tracing
            opa_endpoint: OPA server endpoint for policy evaluation
            policies: List of Policy objects defining available policies
            log_file: File path for logging output
            trace_console: Whether to enable console tracing
        """
        if cls._instance is None:
            cls._instance = ContextManager(service_name,
                                           otel_endpoint=otel_endpoint,
                                           opa_endpoint=opa_endpoint,
                                           policies=policies,
                                           log_file=log_file,
                                           trace_console=trace_console)

    @classmethod
    def get_current(cls) -> Optional[ContextManager]:
        """Get current context manager instance"""
        if cls._instance is None:
            raise RuntimeError("ObservabilityContext not initialized")
        return cls._instance

    @classmethod
    def create_session(cls,
                       session_id: str,
                       initial_context: Optional[Dict] = None) -> TraceContext:
        """Create a new session context"""
        if cls._instance is None:
            raise RuntimeError("ObservabilityContext not initialized")
        return cls._instance.create_session(session_id, initial_context)

    @classmethod
    def set_user_id(cls, user_id: Optional[str]) -> None:
        """Set the user ID for all new traces"""
        if cls._instance is None:
            raise RuntimeError("ObservabilityContext not initialized")
        cls._instance.set_user_id(user_id)

    @classmethod
    def get_user_id(cls) -> Optional[str]:
        """Get the current user ID"""
        if cls._instance is None:
            raise RuntimeError("ObservabilityContext not initialized")
        return cls._instance.get_user_id()
