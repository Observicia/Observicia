"""
Logging utilities for Observicia SDK with console output support.
"""

import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from opentelemetry.trace import get_current_span, SpanContext
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, ConsoleLogExporter
import json


class ConsoleFormatter(logging.Formatter):
    """
    Custom formatter for console output that includes trace context and timestamps.
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


class ObserviciaLogger:
    """
    Logger class that supports both console and OpenTelemetry logging.
    """

    def __init__(self,
                 service_name: str,
                 log_level: int = logging.INFO,
                 console_output: bool = False,
                 otlp_endpoint: Optional[str] = None):
        self.logger = logging.getLogger(service_name)
        self.logger.setLevel(log_level)

        # Clear any existing handlers
        self.logger.handlers = []

        if console_output:
            # Console handler with custom formatter
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(ConsoleFormatter())
            self.logger.addHandler(console_handler)

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
