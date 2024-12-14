"""
Logging utilities for Observicia SDK.
"""

import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional, Union, Literal, Sequence, TYPE_CHECKING
import json
import os
from pathlib import Path
import threading
import sqlite3
from abc import ABC, abstractmethod
from opentelemetry import trace
from opentelemetry.trace import SpanContext
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, ConsoleLogExporter
from opentelemetry.sdk.trace.export import SpanExporter
from opentelemetry.sdk.trace import ReadableSpan

if TYPE_CHECKING:
    from ..core.context_manager import ObservabilityContext


class BaseFormatter(ABC):
    """Base class for all telemetry formatters."""

    @abstractmethod
    def format(self, record: Dict[str, Any]) -> str:
        """Format the record into string representation."""
        pass

    @abstractmethod
    def write(self, formatted_record: str) -> None:
        """Write the formatted record to the output destination."""
        pass


class JsonFormatter(BaseFormatter):
    """JSON formatter for structured telemetry data."""

    def __init__(self, service_name: str):
        self.service_name = service_name

    def format(self, record: Dict[str, Any]) -> str:
        log_data = {
            'timestamp':
            datetime.fromtimestamp(
                record.get('timestamp',
                           datetime.utcnow().timestamp())).isoformat(),
            'level':
            record.get('level', 'INFO'),
            'service':
            self.service_name,
            'message':
            record.get('message', ''),
            'trace_context':
            record.get('trace_context', {}),
            'extra':
            record.get('extra', {})
        }
        return json.dumps(log_data)

    def write(self, formatted_record: str) -> None:
        print(formatted_record)


class ChatFormatter(BaseFormatter):
    """Formatter for chat-specific telemetry."""

    def __init__(self, service_name: str):
        self.service_name = service_name

    def format(self, record: Dict[str, Any]) -> str:
        log_data = {
            'timestamp':
            datetime.fromtimestamp(
                record.get('timestamp',
                           datetime.utcnow().timestamp())).isoformat(),
            'service':
            self.service_name,
            'interaction_type':
            record.get('interaction_type', 'unknown'),
            'content':
            record.get('message', ''),
            'metadata':
            record.get('metadata', {}),
            'trace_context':
            record.get('trace_context', {})
        }
        return json.dumps(log_data)

    def write(self, formatted_record: str) -> None:
        print(formatted_record)


class FileFormatter(BaseFormatter):
    """Formatter for file-based telemetry output."""

    def __init__(self, service_name: str, file_path: str):
        self.service_name = service_name
        self.file_path = file_path
        self.file_handler = logging.FileHandler(file_path)
        self.file_handler.setFormatter(logging.Formatter('%(message)s'))

    def format(self, record: Dict[str, Any]) -> str:
        log_data = {
            'timestamp':
            datetime.fromtimestamp(
                record.get('timestamp',
                           datetime.utcnow().timestamp())).isoformat(),
            'service':
            self.service_name,
            **record
        }
        return json.dumps(log_data)

    def write(self, formatted_record: str) -> None:
        self.file_handler.emit(logging.makeLogRecord({'msg':
                                                      formatted_record}))


class SqliteFormatter(BaseFormatter):
    """SQLite formatter for local development telemetry storage."""

    def __init__(self, service_name: str, database_path: str):
        self.service_name = service_name
        self.database_path = database_path
        self.lock = threading.Lock()
        self._initialize_database()

    def _initialize_database(self) -> None:
        """Initialize SQLite database with required schema."""
        with self.lock:
            with sqlite3.connect(self.database_path) as conn:
                cursor = conn.cursor()

                # Create telemetry table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    service_name TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT,
                    trace_id TEXT,
                    span_id TEXT,
                    parent_span_id TEXT,
                    attributes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # Create spans table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS spans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trace_id TEXT NOT NULL,
                    span_id TEXT NOT NULL,
                    parent_span_id TEXT,
                    name TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    attributes TEXT,
                    status TEXT,
                    service_name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # Create metrics table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    service_name TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    labels TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # Create indices
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON telemetry(timestamp)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_spans_trace_id ON spans(trace_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp)"
                )

                conn.commit()

    def format(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Format record for SQLite storage."""
        if record.get('type') == 'span':
            return {
                'table': 'spans',
                'data': {
                    'trace_id': record.get('trace_id'),
                    'span_id': record.get('span_id'),
                    'parent_span_id': record.get('parent_id'),
                    'name': record.get('name'),
                    'start_time': record.get('start_time'),
                    'end_time': record.get('end_time'),
                    'attributes': json.dumps(record.get('attributes', {})),
                    'status': json.dumps(record.get('status', {})),
                    'service_name': self.service_name
                }
            }
        elif record.get('type') == 'metric':
            return {
                'table': 'metrics',
                'data': {
                    'timestamp':
                    datetime.fromtimestamp(
                        record.get('timestamp',
                                   datetime.utcnow().timestamp())).isoformat(),
                    'service_name':
                    self.service_name,
                    'metric_name':
                    record.get('metric_name'),
                    'metric_value':
                    record.get('metric_value'),
                    'labels':
                    json.dumps(record.get('labels', {}))
                }
            }
        else:
            return {
                'table': 'telemetry',
                'data': {
                    'timestamp':
                    datetime.fromtimestamp(
                        record.get('timestamp',
                                   datetime.utcnow().timestamp())).isoformat(),
                    'service_name':
                    self.service_name,
                    'level':
                    record.get('level', 'INFO'),
                    'message':
                    record.get('message', ''),
                    'trace_id':
                    record.get('trace_context', {}).get('trace_id'),
                    'span_id':
                    record.get('trace_context', {}).get('span_id'),
                    'parent_span_id':
                    record.get('trace_context', {}).get('parent_span_id'),
                    'attributes':
                    json.dumps(record.get('attributes', {}))
                }
            }

    def write(self, formatted_record: Dict[str, Any]) -> None:
        """Write formatted record to SQLite database."""
        table = formatted_record['table']
        data = formatted_record['data']

        with self.lock:
            try:
                with sqlite3.connect(self.database_path) as conn:
                    cursor = conn.cursor()
                    placeholders = ','.join(['?' for _ in data])
                    columns = ','.join(data.keys())
                    values = tuple(data.values())
                    query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
                    cursor.execute(query, values)
                    conn.commit()
            except sqlite3.Error as e:
                print(f"Error writing to SQLite database: {e}")


class FileSpanExporter(SpanExporter):
    """SpanExporter that writes spans to a file or database."""

    def __init__(self, formatter: BaseFormatter):
        self.formatter = formatter

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
        """Export the spans using the configured formatter."""
        try:
            for span in spans:
                span_data = self._extract_span_data(span)
                formatted_data = self.formatter.format(span_data)
                self.formatter.write(formatted_data)
            return None
        except Exception as e:
            print(f"Error exporting spans: {e}")
            return None

    def force_flush(self, timeout_millis: float = 30000) -> bool:
        """Force flush the exporter."""
        return True

    def shutdown(self) -> None:
        """Shutdown the exporter."""
        pass


class ObserviciaLogger:
    """Logger class that supports multiple output formats and destinations."""

    def __init__(self,
                 service_name: str,
                 logging_config: Dict[str, Any],
                 context: Optional['ObservabilityContext'] = None):
        """Initialize the logger with the configuration."""
        self.service_name = service_name
        self.logger = logging.getLogger(service_name)
        self._context = context

        # Configure based on messages settings
        messages_config = logging_config.get("messages", {})
        if messages_config.get("enabled", True):
            self.logger.setLevel(
                getattr(logging, messages_config.get("level", "INFO")))
        else:
            self.logger.setLevel(logging.CRITICAL)

        # Clear any existing handlers
        self.logger.handlers = []

        # Initialize formatters based on configuration
        telemetry_config = logging_config.get("telemetry", {})
        if telemetry_config.get("enabled", True):
            format_type = telemetry_config.get("format", "json")

            if format_type == "sqlite":
                database_path = telemetry_config.get("database_path")
                if not database_path:
                    database_path = str(Path.home() / '.observicia' /
                                        'telemetry.db')
                    os.makedirs(os.path.dirname(database_path), exist_ok=True)
                self.formatter = SqliteFormatter(service_name, database_path)
            else:
                self.formatter = JsonFormatter(service_name)

            # Set up telemetry export
            logger_provider = LoggerProvider()
            set_logger_provider(logger_provider)

            if logging_config.get("file"):
                telemetry_handler = BatchLogRecordProcessor(
                    FileSpanExporter(self.formatter))
                logger_provider.add_log_record_processor(telemetry_handler)

        # Configure chat logging if enabled
        chat_config = logging_config.get("chat", {})
        if chat_config.get("enabled") and chat_config.get("file"):
            self.chat_logger = logging.getLogger(f"{service_name}_chat")
            self.chat_logger.setLevel(logging.INFO)
            chat_handler = logging.FileHandler(chat_config["file"])
            chat_formatter = ChatFormatter(service_name)
            chat_handler.setFormatter(logging.Formatter('%(message)s'))
            self.chat_logger.addHandler(chat_handler)
        else:
            self.chat_logger = None

        self.chat_level = chat_config.get("level", "none")

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
            interaction_type: Literal['prompt', 'completion', 'system'],
            content: str,
            metadata: Optional[Dict[str, Any]] = None) -> None:
        """Log a chat interaction."""
        if not self.chat_logger or interaction_type not in [
                'prompt', 'completion', 'system'
        ]:
            return

        if self.chat_level == 'both' or self.chat_level == interaction_type or interaction_type == 'system':
            trace_context = self._get_trace_context()

            # Get current active transaction if available
            current_transaction = None
            if hasattr(self, '_context') and self._context:
                active_transactions = self._context.get_active_transactions()
                if active_transactions:
                    current_transaction = next(
                        iter(active_transactions.values()))

            tx_metadata = metadata or {}
            if current_transaction:
                tx_metadata.update({
                    'transaction_id':
                    current_transaction.id,
                    'transaction_parent_id':
                    current_transaction.parent_id
                })

            record = {
                'timestamp': datetime.utcnow().timestamp(),
                'interaction_type': interaction_type,
                'message': content,
                'trace_context': trace_context,
                'metadata': tx_metadata
            }

            formatted_record = self.formatter.format(record)
            self.formatter.write(formatted_record)

    def _log(self,
             level: int,
             message: str,
             extra: Optional[Dict[str, Any]] = None,
             exc_info: Any = None) -> None:
        """Internal logging method with trace context and formatting."""
        trace_context = self._get_trace_context()

        record = {
            'timestamp': datetime.utcnow().timestamp(),
            'level': logging.getLevelName(level),
            'message': message,
            'trace_context': trace_context,
            'extra': extra or {}
        }

        # Format and write using the configured formatter
        formatted_record = self.formatter.format(record)
        self.formatter.write(formatted_record)

        # Also log to console if configured
        if hasattr(self, 'logger'):
            self.logger.log(level,
                            message,
                            extra={
                                'trace_context': trace_context,
                                **(extra or {})
                            },
                            exc_info=exc_info)

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

    def cleanup(self) -> None:
        """Cleanup resources and close handlers."""
        if hasattr(self, 'logger'):
            for handler in self.logger.handlers:
                handler.close()

        if hasattr(self, 'chat_logger') and self.chat_logger:
            for handler in self.chat_logger.handlers:
                handler.close()
