"""
Logging utilities for Observicia SDK.
"""

import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional, Union, Literal, Sequence, TYPE_CHECKING
import json
from opentelemetry import trace
from opentelemetry.trace import SpanContext
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, ConsoleLogExporter
from opentelemetry.sdk.trace.export import SpanExporter
from opentelemetry.sdk.trace import ReadableSpan

if TYPE_CHECKING:
    from ..core.context_manager import ObservabilityContext


class FileSpanExporter(SpanExporter):
    """SpanExporter that writes spans to a file in JSON format."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        # Configure file logger for spans
        self.logger = logging.getLogger("SpanExporter")
        self.logger.setLevel(logging.INFO)

        # Create file handler
        file_handler = logging.FileHandler(file_path)
        file_handler.setFormatter(
            logging.Formatter('%(message)s')  # Raw message for JSON
        )
        self.logger.addHandler(file_handler)

        # Remove any existing handlers to avoid duplicate output
        for handler in self.logger.handlers[:-1]:
            self.logger.removeHandler(handler)

    def _extract_span_data(self, span: ReadableSpan) -> Dict[str, Any]:
        """Extract relevant data from a span for serialization."""
        ctx = span.get_span_context()

        # Convert attributes to serializable format
        attributes = {}
        for key, value in span.attributes.items():
            if isinstance(value, (str, int, float, bool)):
                attributes[key] = value
            else:
                attributes[key] = str(value)

        # Extract events
        events = []
        for event in span.events:
            event_data = {
                "name": event.name,
                "timestamp": event.timestamp,
                "attributes": {
                    k: str(v) if not isinstance(v,
                                                (str, int, float, bool)) else v
                    for k, v in event.attributes.items()
                }
            }
            events.append(event_data)

        # Build span data structure
        span_data = {
            "type": "span",
            "timestamp": datetime.utcnow().isoformat(),
            "name": span.name,
            "trace_id": format(ctx.trace_id, "032x"),
            "span_id": format(ctx.span_id, "016x"),
            "parent_id":
            format(span.parent.span_id, "016x") if span.parent else None,
            "start_time": span.start_time,
            "end_time": span.end_time,
            "attributes": attributes,
            "status": {
                "status_code": span.status.status_code.name,
                "description": span.status.description
            },
            "events": events
        }

        return span_data

    def export(self, spans: Sequence[ReadableSpan]) -> None:
        """Export the spans to file."""
        try:
            for span in spans:
                span_data = self._extract_span_data(span)
                self.logger.info(json.dumps(span_data))
            return None
        except Exception as e:
            print(f"Error exporting spans to file: {e}")
            return None

    def force_flush(self, timeout_millis: float = 30000) -> bool:
        """Force flush the exporter."""
        return True

    def shutdown(self) -> None:
        """Shutdown the exporter."""
        for handler in self.logger.handlers:
            handler.close()


class JsonFormatter(logging.Formatter):
    """Custom JSON formatter for main logging."""

    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'service': self.service_name,
            'message': record.getMessage(),
            'trace_context': getattr(record, 'trace_context', {}),
            'extra': getattr(record, 'extra', {})
        }
        return json.dumps(log_data)


class ChatFormatter(logging.Formatter):
    """Custom JSON formatter for chat logging."""

    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record into JSON."""
        # Build base log data
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'service': self.service_name,
            'interaction_type': getattr(record, 'interaction_type', 'unknown'),
            'content': record.getMessage(),
        }

        # Add metadata if present
        metadata = getattr(record, 'metadata', {})
        if metadata:
            log_data['metadata'] = metadata

        # Add trace context if present
        trace_context = getattr(record, 'trace_context', {})
        if trace_context:
            log_data['trace_context'] = trace_context

        return json.dumps(log_data)


class ObserviciaLogger:
    """Logger class that supports file-based logging and OpenTelemetry integration."""

    def __init__(self,
                 service_name: str,
                 logging_config: Dict[str, Any],
                 context: Optional['ObservabilityContext'] = None):
        """
        Initialize the logger with the new configuration structure.
        
        Args:
            service_name: Name of the service
            logging_config: Logging configuration dictionary containing telemetry, messages, and chat settings
            context: ObservabilityContext instance for transaction tracking
        """
        self.service_name = service_name
        self.logger = logging.getLogger(service_name)
        self._context = context or ObservabilityContext.get_current()

        # Configure based on messages settings
        messages_config = logging_config.get("messages", {})
        if messages_config.get("enabled", True):
            self.logger.setLevel(
                getattr(logging, messages_config.get("level", "INFO")))
        else:
            self.logger.setLevel(logging.CRITICAL)  # Effectively disable

        # Clear any existing handlers
        self.logger.handlers = []

        # Main log file handler
        if logging_config.get("file"):
            file_handler = logging.FileHandler(logging_config["file"])
            file_handler.setFormatter(JsonFormatter(service_name))
            self.logger.addHandler(file_handler)

        # Configure chat logging
        chat_config = logging_config.get("chat", {})
        if chat_config.get("enabled") and chat_config.get("file"):
            self.chat_logger = logging.getLogger(f"{service_name}_chat")
            self.chat_logger.setLevel(logging.INFO)
            chat_handler = logging.FileHandler(chat_config["file"])
            chat_handler.setFormatter(ChatFormatter(service_name))
            self.chat_logger.addHandler(chat_handler)
        else:
            self.chat_logger = None

        self.chat_level = chat_config.get("level", "none")

        # Configure telemetry if enabled
        telemetry_config = logging_config.get("telemetry", {})
        if telemetry_config.get("enabled", True):
            logger_provider = LoggerProvider()
            set_logger_provider(logger_provider)

            if logging_config.get("file"):
                telemetry_handler = BatchLogRecordProcessor(
                    FileSpanExporter(logging_config["file"]))
                logger_provider.add_log_record_processor(telemetry_handler)

    def _get_trace_context(self) -> Dict[str, str]:
        """Get current trace context if available."""
        span = trace.get_current_span()
        if span:
            ctx: SpanContext = span.get_span_context()
            return {
                "trace_id": format(ctx.trace_id, "032x"),
                "span_id": format(ctx.span_id, "016x")
            }
        return {}

    def _get_trace_context(self) -> Dict[str, str]:
        """Get current trace context if available."""
        span = trace.get_current_span()
        if span:
            ctx: SpanContext = span.get_span_context()
            return {
                "trace_id": format(ctx.trace_id, "032x"),
                "span_id": format(ctx.span_id, "016x")
            }
        return {}

    def log_chat_interaction(
            self,
            interaction_type: Literal['prompt', 'completion'],
            content: str,
            metadata: Optional[Dict[str, Any]] = None) -> None:
        """Log a chat interaction based on configuration."""
        if not self.chat_logger or interaction_type not in [
                'prompt', 'completion', 'system'
        ]:
            return

        if self.chat_level == 'both' or self.chat_level == interaction_type or interaction_type == 'system':
            # Get current user ID from context
            user_id = None
            if hasattr(self, '_context') and self._context:
                user_id = self._context.get_user_id()

            # Get current active transaction if available
            current_transaction = None
            if hasattr(self, '_context') and self._context:
                active_transactions = self._context.get_active_transactions()
                if active_transactions:
                    # Get the most recent transaction
                    current_transaction = next(
                        iter(active_transactions.values()))

            # Build metadata with transaction information
            tx_metadata = metadata or {}
            if current_transaction:
                tx_metadata.update({
                    'transaction_id':
                    current_transaction.id,
                    'transaction_parent_id':
                    current_transaction.parent_id
                })

            extra = {
                'interaction_type': interaction_type,
                'metadata': tx_metadata,
                'user_id': user_id
            }

            self.chat_logger.info(content, extra=extra)

    def _log(self,
             level: int,
             message: str,
             extra: Optional[Dict[str, Any]] = None,
             exc_info: Any = None) -> None:
        """Internal logging method with trace context."""
        trace_context = self._get_trace_context()

        extra_dict = {'trace_context': trace_context}
        if extra:
            extra_dict.update(extra)

        self.logger.log(level, message, extra=extra_dict, exc_info=exc_info)

    # Standard logging methods
    def debug(self,
              message: str,
              extra: Optional[Dict[str, Any]] = None) -> None:
        self._log(logging.DEBUG, message, extra)

    def info(self,
             message: str,
             extra: Optional[Dict[str, Any]] = None) -> None:
        self._log(logging.INFO, message, extra)

    def warning(self,
                message: str,
                extra: Optional[Dict[str, Any]] = None) -> None:
        self._log(logging.WARNING, message, extra)

    def error(self,
              message: str,
              extra: Optional[Dict[str, Any]] = None,
              exc_info: Any = None) -> None:
        self._log(logging.ERROR, message, extra, exc_info)

    def critical(self,
                 message: str,
                 extra: Optional[Dict[str, Any]] = None,
                 exc_info: Any = None) -> None:
        self._log(logging.CRITICAL, message, extra, exc_info)
