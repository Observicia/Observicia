"""
logging utilities for Observicia SDK.
"""

import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional, Union, Literal
from opentelemetry.trace import get_current_span, SpanContext
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, ConsoleLogExporter
from opentelemetry.sdk.trace.export import SpanExporter
from opentelemetry.sdk.trace import ReadableSpan
from typing import Sequence

import json


class ConsoleFormatter(logging.Formatter):
    """
    Custom formatter for console and file output that includes trace context and timestamps.
    """

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).isoformat()

        # Get trace context if available
        trace_context = getattr(record, 'trace_context', {})
        trace_id = trace_context.get('trace_id', '')
        span_id = trace_context.get('span_id', '')

        # Format the basic message
        log_entry = {
            'timestamp': timestamp,
            'level': record.levelname,
            'name': record.name,
            'message': record.getMessage(),
        }

        # Add trace context if available
        if trace_id:
            log_entry['trace_id'] = trace_id
        if span_id:
            log_entry['span_id'] = span_id

        # Add extra fields if available
        extra = getattr(record, 'extra', None)
        if extra:
            log_entry['extra'] = extra

        # Add exception info if available
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_entry, indent=2)


class FileSpanExporter(SpanExporter):
    """
    SpanExporter that writes spans to a file in JSON format.
    """

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


class ChatInteractionFormatter(logging.Formatter):
    """
    Custom formatter for chat interactions that includes trace context and metadata.
    """

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).isoformat()

        # Get trace context if available
        trace_context = getattr(record, 'trace_context', {})

        # Format the interaction log entry
        log_entry = {
            'timestamp': timestamp,
            'level': record.levelname,
            'service_name': getattr(record, 'service_name', 'unknown'),
            'user_id': getattr(record, 'user_id', 'unknown'),
            'transaction_id': trace_context.get('trace_id', ''),
            'span_id': trace_context.get('span_id', ''),
            'interaction_type': getattr(record, 'interaction_type', 'unknown'),
            'content': record.getMessage(),
        }

        # Add metadata if available
        metadata = getattr(record, 'metadata', None)
        if metadata:
            log_entry['metadata'] = metadata

        return json.dumps(log_entry)


class ObserviciaLogger:
    """
    Logger class that supports console, file, and OpenTelemetry logging.
    """

    def __init__(self,
                 service_name: str,
                 log_level: int = logging.INFO,
                 console_output: bool = False,
                 file_output: Optional[str] = None,
                 chat_log_level: Literal['none', 'prompt', 'completion',
                                         'both'] = 'none',
                 chat_log_file: Optional[str] = None,
                 otlp_endpoint: Optional[str] = None):
        """
        Initialize the logger with multiple output options.
        
        Args:
            service_name: Name of the service
            log_level: Logging level (default: INFO)
            console_output: Whether to output to console
            file_output: File path for log output (optional)
            chat_log_level: Level of chat interaction logging (default: none)
            chat_log_file: Separate file for chat interactions (optional)
            otlp_endpoint: OpenTelemetry endpoint (optional)
        """
        self.service_name = service_name
        self.logger = logging.getLogger(service_name)
        self.logger.setLevel(log_level)
        self.chat_log_level = chat_log_level

        # Clear any existing handlers
        self.logger.handlers = []

        # Create formatter
        formatter = ConsoleFormatter()

        if console_output:
            # Console handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

        if file_output:
            # File handler
            file_handler = logging.FileHandler(file_output)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

        if chat_log_level != 'none' and chat_log_file:
            self.chat_logger = logging.getLogger(f"{service_name}_chat")
            self.chat_logger.setLevel(log_level)
            chat_handler = logging.FileHandler(chat_log_file)
            chat_handler.setFormatter(ChatInteractionFormatter())
            self.chat_logger.addHandler(chat_handler)
        else:
            self.chat_logger = None

        if otlp_endpoint:
            # OpenTelemetry setup
            logger_provider = LoggerProvider()
            set_logger_provider(logger_provider)

            # Console exporter for OpenTelemetry
            console_exporter = ConsoleLogExporter()
            logger_provider.add_log_record_processor(
                BatchLogRecordProcessor(console_exporter))

    def _get_trace_context(self) -> Dict[str, str]:
        """Get current trace context if available."""
        span = get_current_span()
        if span:
            ctx: SpanContext = span.get_span_context()
            return {
                "trace_id": format(ctx.trace_id, "032x"),
                "span_id": format(ctx.span_id, "016x"),
            }
        return {}

    def log_chat_interaction(self,
                             interaction_type: Literal['prompt', 'completion'],
                             content: str,
                             metadata: Optional[Dict[str, Any]] = None,
                             user_id: Optional[str] = None) -> None:
        """
        Log a chat interaction with trace context and metadata.
        
        Args:
            interaction_type: Type of interaction (prompt or completion)
            content: The actual content to log
            metadata: Additional metadata for the interaction
            user_id: User ID associated with the interaction
        """
        if not self.chat_logger or interaction_type not in [
                'prompt', 'completion'
        ]:
            return

        if self.chat_log_level == 'both' or self.chat_log_level == interaction_type:
            trace_context = self._get_trace_context()

            # Create extra attributes
            extra = {
                'trace_context': trace_context,
                'service_name': self.service_name,
                'interaction_type': interaction_type,
                'user_id': user_id,
                'metadata': metadata
            }

            self.chat_logger.info(content, extra=extra)

    def _log(self,
             level: int,
             message: str,
             extra: Optional[Dict[str, Any]] = None,
             exc_info: Any = None) -> None:
        """
        Log a message with trace context and additional attributes.
        """
        trace_context = self._get_trace_context()

        # Create record extras
        extra_dict = {}
        if trace_context:
            extra_dict['trace_context'] = trace_context
        if extra:
            extra_dict['extra'] = extra

        self.logger.log(level, message, extra=extra_dict, exc_info=exc_info)

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
