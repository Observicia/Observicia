import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export import ConsoleSpanExporter

from observicia.core.context_manager import (ObservabilityContext,
                                             ContextManager, TraceContext)
from observicia.core.policy_engine import PolicyEngine, PolicyResult


@pytest.fixture
def mock_policy_engine():
    engine = Mock(spec=PolicyEngine)
    engine.evaluate_with_context = AsyncMock(
        return_value=PolicyResult(passed=True, violations=[]))
    return engine


@pytest.fixture
def context_manager():
    return ContextManager(service_name="test-service", trace_console=True)


@pytest.fixture
def trace_context():
    return TraceContext(trace_id="test-trace-id",
                        parent_id="test-parent-id",
                        attributes={"test_key": "test_value"},
                        session_id="test-session")


class TestTraceContext:

    def test_initialization(self):
        context = TraceContext(trace_id="test-trace",
                               parent_id="parent-id",
                               attributes={"key": "value"})

        assert context.trace_id == "test-trace"
        assert context.parent_id == "parent-id"
        assert context.attributes == {"key": "value"}
        assert context.violation_count == 0
        assert len(context.active_policies) == 0
        assert len(context.policy_results) == 0

    def test_to_dict(self):
        context = TraceContext(trace_id="test-trace",
                               parent_id="parent-id",
                               attributes={"key": "value"},
                               session_id="test-session")

        result = context.to_dict()
        assert result["trace_id"] == "test-trace"
        assert result["parent_id"] == "parent-id"
        assert result["session_id"] == "test-session"
        assert result["key"] == "value"
        assert isinstance(result["active_policies"], list)

    def test_add_violation(self):
        context = TraceContext(trace_id="test-trace",
                               parent_id="parent-id",
                               attributes={})

        policy_result = PolicyResult(
            passed=False, violations=["test violation 1", "test violation 2"])

        context.add_violation(policy_result)
        assert context.violation_count == 2
        assert len(context.policy_results) == 1
        assert context.policy_results[0] == policy_result

    def test_policy_management(self):
        context = TraceContext(trace_id="test-trace",
                               parent_id="parent-id",
                               attributes={})

        context.add_policy("test_policy")
        assert "test_policy" in context.active_policies

        context.remove_policy("test_policy")
        assert "test_policy" not in context.active_policies

        # Test removing non-existent policy
        context.remove_policy("non_existent")
        assert len(context.active_policies) == 0


class TestContextManager:

    def test_initialization(self):
        # Get the current tracer provider before creating context manager
        original_provider = trace.get_tracer_provider()

        manager = ContextManager(service_name="test-service",
                                 trace_console=True)

        # Verify that a tracer was created
        assert manager._tracer is not None
        assert manager._service_name == "test-service"

        # Verify that the provider was changed
        current_provider = trace.get_tracer_provider()
        assert isinstance(current_provider, TracerProvider)
        assert current_provider != original_provider

    def test_get_non_existent_session(self, context_manager):
        session = context_manager.get_session("non-existent")
        assert session is None

    def test_create_and_get_session(self, context_manager):
        session_id = "test-session"
        initial_context = {"test_key": "test_value"}

        context = context_manager.create_session(
            session_id=session_id, initial_context=initial_context)

        assert context.session_id == session_id
        assert context.attributes == initial_context

        # Verify we can retrieve the same session
        retrieved = context_manager.get_session(session_id)
        assert retrieved == context
        assert retrieved.attributes == initial_context

    @pytest.mark.asyncio
    async def test_create_span(self, context_manager, trace_context):
        span_name = "test-span"
        attributes = {"test_attr": "test_value"}

        span = await context_manager.create_span(name=span_name,
                                                 context=trace_context,
                                                 kind=SpanKind.CLIENT,
                                                 attributes=attributes)

        assert span is not None
        assert span.name == span_name
        assert span.kind == SpanKind.CLIENT

        # Check that context attributes were added to span
        span_attrs = dict(span.attributes)
        assert span_attrs["service.name"] == "test-service"
        assert span_attrs["test_attr"] == "test_value"
        assert span_attrs["trace_id"] == trace_context.trace_id

    @pytest.mark.asyncio
    async def test_policy_evaluation(self, context_manager, trace_context,
                                     mock_policy_engine):
        context_manager.policy_engine = mock_policy_engine
        eval_context = {"test": "context"}

        result = await context_manager.evaluate_policies(
            context=trace_context,
            eval_context=eval_context,
            policies=["test_policy"])

        assert result.passed is True
        assert len(result.violations) == 0
        mock_policy_engine.evaluate_with_context.assert_called_once_with(
            eval_context=eval_context, policies=["test_policy"])

    @pytest.mark.asyncio
    async def test_policy_evaluation_with_violations(self, context_manager,
                                                     trace_context,
                                                     mock_policy_engine):
        violation = "test violation"
        mock_policy_engine.evaluate_with_context.return_value = PolicyResult(
            passed=False, violations=[violation])

        context_manager.policy_engine = mock_policy_engine

        result = await context_manager.evaluate_policies(
            context=trace_context, eval_context={}, policies=["test_policy"])

        assert result.passed is False
        assert violation in result.violations
        assert trace_context.violation_count == 1


class TestObservabilityContext:

    def test_singleton_behavior(self):
        ObservabilityContext._instance = None  # Reset singleton

        # First initialization
        ObservabilityContext.initialize(service_name="test-service")
        first_instance = ObservabilityContext.get_current()

        # Second initialization shouldn't create new instance
        ObservabilityContext.initialize(service_name="another-service")
        second_instance = ObservabilityContext.get_current()

        assert first_instance is second_instance
        assert first_instance._service_name == "test-service"

    def test_uninitialized_access(self):
        ObservabilityContext._instance = None  # Reset singleton

        with pytest.raises(RuntimeError) as exc_info:
            ObservabilityContext.get_current()
        assert "ObservabilityContext not initialized" in str(exc_info.value)

    def test_create_session_uninitialized(self):
        ObservabilityContext._instance = None  # Reset singleton

        with pytest.raises(RuntimeError) as exc_info:
            ObservabilityContext.create_session("test-session")
        assert "ObservabilityContext not initialized" in str(exc_info.value)

    def test_initialization_with_options(self):
        ObservabilityContext._instance = None  # Reset singleton

        ObservabilityContext.initialize(
            service_name="test-service",
            otel_endpoint="http://localhost:4317",
            opa_endpoint="http://localhost:8181",
            default_policies=["policy1", "policy2"],
            trace_console=True)

        instance = ObservabilityContext.get_current()
        assert instance._service_name == "test-service"
        assert instance.policy_engine is not None
        assert instance._default_policies == ["policy1", "policy2"]


if __name__ == '__main__':
    pytest.main([__file__])
