"""
Utility functions and helpers for the Observicia SDK.
Provides common functionality used across the SDK components.
"""

import json
import re
import tiktoken
from typing import Any, Dict, Optional, Union
from datetime import datetime
from contextvars import ContextVar
import numpy as np

from opentelemetry.trace import get_current_span as otel_get_current_span
from opentelemetry.trace import Span, SpanContext
from opentelemetry.baggage import get_all as get_baggage

# Type alias for trace attributes
TraceAttributes = Dict[str, Union[str, int, float, bool]]


def get_current_span() -> Optional[Span]:
    """
    Get the current active span from the trace context.
    
    Returns:
        Optional[Span]: The current span or None if no span is active
    """
    span = otel_get_current_span()
    if span and span.is_recording():
        return span
    return None


def get_current_context() -> Dict[str, Any]:
    """
    Get the current context including trace and baggage information.
    
    Returns:
        Dict[str, Any]: Dictionary containing current context information
    """
    span = get_current_span()
    context = {
        "trace_id": None,
        "span_id": None,
        "baggage": get_baggage(),
        "timestamp": datetime.utcnow().isoformat()
    }

    if span:
        span_context: SpanContext = span.get_span_context()
        context.update({
            "trace_id": format_trace_id(span_context.trace_id),
            "span_id": format_span_id(span_context.span_id)
        })

    return context


def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """
    Count tokens in text using the appropriate tokenizer for the model.
    
    Args:
        text (str): Text to count tokens for
        model (str): Model name to determine tokenizer
        
    Returns:
        int: Number of tokens in the text
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except KeyError:
        # Fallback to cl100k_base for unknown models
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception as e:
        # Log error and return approximate token count
        print(f"Error counting tokens: {e}")
        return len(text.split())  # Rough approximation


def format_trace_attributes(attributes: Dict[str, Any]) -> TraceAttributes:
    """
    Format attributes to be compatible with OpenTelemetry trace attributes.
    
    Args:
        attributes (Dict[str, Any]): Raw attributes to format
        
    Returns:
        TraceAttributes: Formatted attributes safe for tracing
    """
    formatted = {}

    for key, value in attributes.items():
        # Ensure key is a string
        key = str(key)

        # Handle different value types
        if isinstance(value, (str, int, float, bool)):
            formatted[key] = value
        elif isinstance(value, (datetime, np.ndarray)):
            formatted[key] = str(value)
        elif isinstance(value, dict):
            formatted[key] = json.dumps(value, default=str)
        elif value is None:
            formatted[key] = "null"
        else:
            formatted[key] = str(value)

    return formatted


def safe_json_serialize(obj: Any) -> str:
    """
    Safely serialize any object to JSON string.
    
    Args:
        obj (Any): Object to serialize
        
    Returns:
        str: JSON string representation of the object
    """

    def default(o: Any) -> str:
        if isinstance(o, (datetime, np.ndarray)):
            return str(o)
        return f"<non-serializable: {type(o).__name__}>"

    try:
        return json.dumps(obj, default=default)
    except Exception as e:
        return f"<serialization-error: {str(e)}>"


def format_trace_id(trace_id: int) -> str:
    """
    Format trace ID as hexadecimal string.
    
    Args:
        trace_id (int): Trace ID as integer
        
    Returns:
        str: Formatted trace ID
    """
    return f"{trace_id:032x}"


def format_span_id(span_id: int) -> str:
    """
    Format span ID as hexadecimal string.
    
    Args:
        span_id (int): Span ID as integer
        
    Returns:
        str: Formatted span ID
    """
    return f"{span_id:016x}"


def sanitize_key(key: str) -> str:
    """
    Sanitize attribute key for use in traces.
    
    Args:
        key (str): Raw attribute key
        
    Returns:
        str: Sanitized key
    """
    # Replace invalid characters with underscore
    sanitized = re.sub(r'[^a-zA-Z0-9._-]', '_', key)
    # Ensure key starts with letter or underscore
    if not sanitized[0].isalpha() and sanitized[0] != '_':
        sanitized = f"_{sanitized}"
    return sanitized


def truncate_string(s: str, max_length: int = 1000) -> str:
    """
    Truncate string to maximum length.
    
    Args:
        s (str): String to truncate
        max_length (int): Maximum length
        
    Returns:
        str: Truncated string
    """
    if len(s) <= max_length:
        return s
    return f"{s[:max_length-3]}..."


class MetricsHelper:
    """Helper class for handling metrics calculations and formatting."""

    @staticmethod
    def calculate_rate(count: int, duration_seconds: float) -> float:
        """Calculate rate per second."""
        if duration_seconds <= 0:
            return 0.0
        return count / duration_seconds

    @staticmethod
    def format_duration(duration_seconds: float) -> str:
        """Format duration in human readable format."""
        if duration_seconds < 1:
            return f"{duration_seconds*1000:.2f}ms"
        elif duration_seconds < 60:
            return f"{duration_seconds:.2f}s"
        else:
            minutes = int(duration_seconds / 60)
            seconds = duration_seconds % 60
            return f"{minutes}m {seconds:.2f}s"

    @staticmethod
    def calculate_percentile(values: list, percentile: float) -> float:
        """Calculate percentile of values."""
        if not values:
            return 0.0
        return float(np.percentile(values, percentile))


def get_memory_usage() -> Dict[str, float]:
    """
    Get current memory usage statistics.
    
    Returns:
        Dict[str, float]: Memory usage metrics in MB
    """
    import psutil
    process = psutil.Process()
    memory_info = process.memory_info()

    return {
        "rss_mb": memory_info.rss / (1024 * 1024),
        "vms_mb": memory_info.vms / (1024 * 1024)
    }


def exponential_backoff(attempt: int, base_delay: float = 1.0) -> float:
    """
    Calculate exponential backoff delay.
    
    Args:
        attempt (int): Attempt number (0-based)
        base_delay (float): Base delay in seconds
        
    Returns:
        float: Delay in seconds
    """
    return min(base_delay * (2**attempt), 30.0)  # Cap at 30 seconds


# Global context for thread-local storage
_thread_local = ContextVar("observicia_context", default={})


def get_thread_local() -> Dict[str, Any]:
    """Get thread-local storage dictionary."""
    return _thread_local.get()


def set_thread_local(key: str, value: Any) -> None:
    """Set value in thread-local storage."""
    context = _thread_local.get()
    context[key] = value
    _thread_local.set(context)


def clear_thread_local() -> None:
    """Clear thread-local storage."""
    _thread_local.set({})
