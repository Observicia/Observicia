from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Literal, Any
from datetime import datetime
from uuid import uuid4

from opentelemetry import trace, baggage
from opentelemetry.trace import Span, SpanKind
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

from .policy_engine import PolicyEngine, PolicyResult, Policy
from ..utils.logging import FileSpanExporter, ObserviciaLogger
from ..utils.exporter import SQLiteSpanExporter, RedisSpanExporter


@dataclass
class Transaction:
    """Represents a logical transaction (e.g. multi-round chat conversation)."""
    id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_id: Optional[str] = None


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
    """Manages observability context and tracing."""

    def __init__(self,
                 service_name: str,
                 otel_endpoint: Optional[str] = None,
                 opa_endpoint: Optional[str] = None,
                 policies: Optional[List[Policy]] = None,
                 logging_config: Optional[Dict] = None):
        """
        Initialize the context manager.
        
        Args:
            service_name: Name of the service using the SDK
            otel_endpoint: OpenTelemetry endpoint for tracing
            opa_endpoint: OPA server endpoint for policy evaluation
            policies: List of Policy objects defining available policies
            logging_config: Configuration dictionary for logging options
        """
        self._sessions: Dict[str, TraceContext] = {}
        self._service_name = service_name
        self._current_user_id: Optional[str] = None
        self._active_transactions: Dict[str, Transaction] = {}

        # Initialize policy engine if OPA endpoint is provided
        self.policy_engine = PolicyEngine(
            opa_endpoint=opa_endpoint,
            policies=policies) if opa_endpoint else None

        # Use default logging configuration if none provided
        self._logging_config = logging_config or {
            "file": None,
            "telemetry": {
                "enabled": True,
                "format": "json"
            },
            "messages": {
                "enabled": True,
                "level": "INFO"
            },
            "chat": {
                "enabled": False,
                "level": "none",
                "file": None
            }
        }

        # Initialize logger with new configuration
        self._logger = ObserviciaLogger(service_name=service_name,
                                        logging_config=self._logging_config,
                                        context=self)

        # Set up tracing
        provider = TracerProvider()

        if otel_endpoint and self._logging_config["telemetry"]["enabled"]:
            otlp_processor = BatchSpanProcessor(
                OTLPSpanExporter(endpoint=otel_endpoint))
            provider.add_span_processor(otlp_processor)

        # Add file exporter for telemetry if enabled
        if (self._logging_config["file"]
                and self._logging_config["telemetry"]["enabled"]):
            file_processor = BatchSpanProcessor(
                FileSpanExporter(self._logging_config["file"]))
            provider.add_span_processor(file_processor)

        # Add SQLite exporter if enabled
        if (self._logging_config.get("sqlite", {}).get("enabled", False)
                and self._logging_config["sqlite"].get("database", None)):
            sqlite_processor = BatchSpanProcessor(
                SQLiteSpanExporter(self._logging_config["sqlite"]["database"]))
            provider.add_span_processor(sqlite_processor)

        # Add Redis exporter if enabled
        redis_config = self._logging_config.get("telemetry",
                                                {}).get("redis", {})
        if redis_config.get("enabled", False):
            redis_processor = BatchSpanProcessor(
                RedisSpanExporter(
                    host=redis_config.get("host", "localhost"),
                    port=redis_config.get("port", 6379),
                    db=redis_config.get("db", 0),
                    password=redis_config.get("password"),
                    key_prefix=redis_config.get("key_prefix",
                                                "observicia:telemetry:"),
                    retention_hours=redis_config.get("retention_hours", 24)))
            provider.add_span_processor(redis_processor)
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

    def start_transaction(self,
                          metadata: Optional[Dict[str, Any]] = None,
                          parent_id: Optional[str] = None) -> str:
        """Start a new transaction and return its ID."""
        transaction_id = str(uuid4())
        transaction = Transaction(id=transaction_id,
                                  start_time=datetime.utcnow(),
                                  metadata=metadata or {},
                                  parent_id=parent_id)

        self._active_transactions[transaction_id] = transaction

        if hasattr(self, '_logger'):
            # Log to main logger
            self._logger.info(f"=== Transaction Started: {transaction_id} ===",
                              extra={
                                  'metadata': {
                                      'transaction_id': transaction_id,
                                      'parent_id': parent_id,
                                      'event': 'transaction_start',
                                      **(metadata or {})
                                  }
                              })

            # Log to chat logger
            if hasattr(self._logger,
                       'chat_logger') and self._logger.chat_logger:
                self._logger.log_chat_interaction(
                    interaction_type='system',
                    content=f"=== Begin Transaction: {transaction_id} ===",
                    metadata={
                        'transaction_id': transaction_id,
                        'parent_id': parent_id,
                        'event': 'transaction_start',
                        **(metadata or {})
                    })

        return transaction_id

    def end_transaction(self,
                        transaction_id: str,
                        metadata: Optional[Dict[str, Any]] = None) -> None:
        """End a transaction with the given ID."""
        if transaction_id not in self._active_transactions:
            if hasattr(self, '_logger'):
                self._logger.error(
                    f"Attempt to end non-existent transaction: {transaction_id}"
                )
            raise ValueError(f"Transaction {transaction_id} not found")

        transaction = self._active_transactions[transaction_id]
        transaction.end_time = datetime.utcnow()
        duration = (transaction.end_time -
                    transaction.start_time).total_seconds()

        if metadata:
            transaction.metadata.update(metadata)

        if hasattr(self, '_logger'):
            # Log to main logger
            self._logger.info(f"=== Transaction Ended: {transaction_id} ===",
                              extra={
                                  'metadata': {
                                      'transaction_id': transaction_id,
                                      'parent_id': transaction.parent_id,
                                      'event': 'transaction_end',
                                      'duration_seconds': duration,
                                      **(transaction.metadata or {})
                                  }
                              })

            # Log to chat logger
            if hasattr(self._logger,
                       'chat_logger') and self._logger.chat_logger:
                self._logger.log_chat_interaction(
                    interaction_type='system',
                    content=
                    f"=== End Transaction: {transaction_id} === (Duration: {duration:.2f}s)",
                    metadata={
                        'transaction_id': transaction_id,
                        'parent_id': transaction.parent_id,
                        'event': 'transaction_end',
                        'duration_seconds': duration,
                        **(transaction.metadata or {})
                    })

        del self._active_transactions[transaction_id]

    def get_transaction(self, transaction_id: str) -> Optional[Transaction]:
        """Get transaction details by ID."""
        return self._active_transactions.get(transaction_id)

    def get_active_transactions(self) -> Dict[str, Transaction]:
        """Get all active transactions."""
        return self._active_transactions.copy()

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
                               user_id=self._current_user_id)
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
    """Global context manager singleton."""

    _instance: Optional[ContextManager] = None

    @classmethod
    def initialize(cls,
                   service_name: str,
                   otel_endpoint: Optional[str] = None,
                   opa_endpoint: Optional[str] = None,
                   policies: Optional[List[Policy]] = None,
                   logging_config: Optional[Dict] = None) -> None:
        """Initialize the global context manager."""
        if cls._instance is None:
            cls._instance = ContextManager(service_name,
                                           otel_endpoint=otel_endpoint,
                                           opa_endpoint=opa_endpoint,
                                           policies=policies,
                                           logging_config=logging_config)

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

    @classmethod
    def start_transaction(cls,
                          metadata: Optional[Dict[str, Any]] = None,
                          parent_id: Optional[str] = None) -> str:
        """Start a new transaction."""
        if cls._instance is None:
            raise RuntimeError("ObservabilityContext not initialized")
        return cls._instance.start_transaction(metadata=metadata,
                                               parent_id=parent_id)

    @classmethod
    def end_transaction(cls,
                        transaction_id: str,
                        metadata: Optional[Dict[str, Any]] = None) -> None:
        """End a transaction."""
        if cls._instance is None:
            raise RuntimeError("ObservabilityContext not initialized")
        return cls._instance.end_transaction(transaction_id=transaction_id,
                                             metadata=metadata)

    @classmethod
    def get_transaction(cls, transaction_id: str) -> Optional[Transaction]:
        """Get transaction details."""
        if cls._instance is None:
            raise RuntimeError("ObservabilityContext not initialized")
        return cls._instance.get_transaction(transaction_id)

    @classmethod
    def get_active_transactions(cls) -> Dict[str, Transaction]:
        """Get all active transactions."""
        if cls._instance is None:
            raise RuntimeError("ObservabilityContext not initialized")
        return cls._instance.get_active_transactions()
