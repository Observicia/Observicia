import sqlite3
import redis
from typing import Dict, Any, Optional, Sequence
from datetime import datetime
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter
from opentelemetry.trace import SpanContext


class SQLiteSpanExporter(SpanExporter):
    """SpanExporter that writes spans to a SQLite database."""

    def __init__(self, database_path: str):
        """Initialize SQLite exporter with database path."""
        self.database_path = database_path
        self._initialize_database()

    def _initialize_database(self) -> None:
        """Create the database schema if it doesn't exist."""
        with sqlite3.connect(self.database_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    transaction_id TEXT,
                    user_id TEXT,
                    model TEXT,
                    provider TEXT,
                    request_type TEXT,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    total_tokens INTEGER,
                    duration_ms REAL,
                    success BOOLEAN,
                    trace_id TEXT,
                    span_id TEXT,
                    parent_span_id TEXT
                )
            ''')
            conn.commit()

    def _extract_span_data(self, span: ReadableSpan) -> Dict[str, Any]:
        """Extract relevant data from a span for database insertion."""
        ctx: SpanContext = span.get_span_context()
        attributes = span.attributes or {}

        # Calculate duration in milliseconds
        duration_ms = (span.end_time - span.start_time
                       ) / 1_000_000  # Convert nanoseconds to milliseconds

        return {
            'timestamp':
            datetime.utcfromtimestamp(span.start_time / 1e9).isoformat(),
            'transaction_id':
            attributes.get('transaction_id', ''),
            'user_id':
            attributes.get('user.id', ''),
            'model':
            attributes.get('llm.model', ''),
            'provider':
            attributes.get('llm.provider', ''),
            'request_type':
            attributes.get('llm.request.type', ''),
            'prompt_tokens':
            attributes.get('prompt.tokens', 0),
            'completion_tokens':
            attributes.get('completion.tokens', 0),
            'total_tokens':
            attributes.get('total.tokens', 0),
            'duration_ms':
            duration_ms,
            'success':
            attributes.get('policy.passed', True),
            'trace_id':
            format(ctx.trace_id, '032x'),
            'span_id':
            format(ctx.span_id, '016x'),
            'parent_span_id':
            format(span.parent.span_id, '016x') if span.parent else ''
        }

    def export(self, spans: list[ReadableSpan]) -> None:
        """Export the spans to SQLite database."""
        try:
            with sqlite3.connect(self.database_path) as conn:
                cursor = conn.cursor()

                for span in spans:
                    # Only process completion spans with token data
                    if 'prompt.tokens' in span.attributes:
                        span_data = self._extract_span_data(span)

                        cursor.execute(
                            '''
                            INSERT INTO telemetry (
                                timestamp, transaction_id, user_id, model, provider,
                                request_type, prompt_tokens, completion_tokens,
                                total_tokens, duration_ms, success, trace_id,
                                span_id, parent_span_id
                            ) VALUES (
                                :timestamp, :transaction_id, :user_id, :model, :provider,
                                :request_type, :prompt_tokens, :completion_tokens,
                                :total_tokens, :duration_ms, :success, :trace_id,
                                :span_id, :parent_span_id
                            )
                        ''', span_data)

                conn.commit()
            return None
        except Exception as e:
            print(f"Error exporting spans to SQLite: {e}")
            return None

    def force_flush(self, timeout_millis: float = 30000) -> bool:
        """Force flush the exporter."""
        return True

    def shutdown(self) -> None:
        """Shutdown the exporter."""
        pass


class RedisSpanExporter(SpanExporter):
    """Redis exporter for Observicia telemetry data."""

    def __init__(self,
                 host: str = "localhost",
                 port: int = 6379,
                 db: int = 0,
                 password: Optional[str] = None,
                 key_prefix: str = "observicia:telemetry:",
                 retention_hours: int = 24):
        """
        Initialize Redis exporter.
        
        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            password: Redis password
            key_prefix: Prefix for Redis keys
            retention_hours: Data retention period in hours
        """
        self.redis_client = redis.Redis(host=host,
                                        port=port,
                                        db=db,
                                        password=password,
                                        decode_responses=True)
        self.key_prefix = key_prefix
        self.retention_hours = retention_hours

    def _extract_span_data(self, span: ReadableSpan) -> Dict[str, Any]:
        """Extract telemetry data from span in CSV-compatible format."""
        attrs = span.attributes or {}

        # Calculate duration in milliseconds
        duration_ms = (span.end_time -
                       span.start_time) / 1_000_000  # Convert ns to ms

        data = {
            "timestamp":
            datetime.fromtimestamp(span.start_time / 1e9).isoformat(),
            "transaction_id": str(attrs.get("transaction_id", "")),
            "user_id": str(attrs.get("user.id", "")),
            "model": str(attrs.get("llm.model", "")),
            "provider": str(attrs.get("llm.provider", "")),
            "request_type": str(attrs.get("llm.request.type", "")),
            "prompt_tokens": str(int(attrs.get("prompt.tokens", 0))),
            "completion_tokens": str(int(attrs.get("completion.tokens", 0))),
            "total_tokens": str(int(attrs.get("total.tokens", 0))),
            "duration_ms": str(float(duration_ms)),
            "success": str(attrs.get("policy.passed", True))
        }

        return data

    def export(self, spans: Sequence[ReadableSpan]) -> None:
        """Export spans to Redis."""
        try:
            pipeline = self.redis_client.pipeline()

            for span in spans:
                # Only process completion spans
                if not ('completion' in span.name):
                    continue

                span_data = self._extract_span_data(span)

                # Create a unique key for this span
                span_key = f"{self.key_prefix}{span.start_time}"

                # Store span data as hash
                pipeline.hset(span_key, mapping=span_data)

                # Set expiry
                pipeline.expire(span_key, self.retention_hours * 3600)

            pipeline.execute()
            return None

        except Exception as e:
            print(f"Error exporting spans to Redis: {e}")
            return None

    def force_flush(self, timeout_millis: float = 30000) -> bool:
        """Force flush the exporter."""
        return True

    def shutdown(self) -> None:
        """Shutdown the exporter."""
        self.redis_client.close()
