import pytest
from datetime import datetime
import json
from opentelemetry.trace import SpanKind
from observicia.utils.helpers import (
    count_tokens,
    format_trace_attributes,
    safe_json_serialize,
    format_trace_id,
    format_span_id,
    sanitize_key,
    truncate_string,
    MetricsHelper,
)
from observicia.utils.token_helpers import count_prompt_tokens, count_text_tokens
from observicia.utils.serialization_helpers import (
    serialize_chat_completion,
    serialize_completion,
    serialize_llm_response,
)

def test_count_tokens():
    """Test token counting with different models."""
    text = "Hello, world!"
    
    # Test with standard model
    count = count_tokens(text, "gpt-3.5-turbo")
    assert count > 0
    
    # Test with unknown model (should use fallback)
    count_unknown = count_tokens(text, "unknown-model")
    assert count_unknown > 0

def test_format_trace_attributes():
    """Test attribute formatting for traces."""
    attributes = {
        "string": "value",
        "int": 42,
        "float": 3.14,
        "bool": True,
        "datetime": datetime.now(),
        "dict": {"key": "value"},
        "none": None
    }
    
    formatted = format_trace_attributes(attributes)
    
    assert isinstance(formatted["string"], str)
    assert isinstance(formatted["int"], int)
    assert isinstance(formatted["float"], float)
    assert isinstance(formatted["bool"], bool)
    assert isinstance(formatted["datetime"], str)
    assert isinstance(formatted["dict"], str)
    assert formatted["none"] == "null"

def test_safe_json_serialize():
    """Test JSON serialization with various types."""
    data = {
        "datetime": datetime.now(),
        "regular": "string",
        "nested": {"key": "value"}
    }
    
    serialized = safe_json_serialize(data)
    assert isinstance(serialized, str)
    
    # Test with non-serializable object
    class NonSerializable:
        pass
    
    data_with_nonserializable = {"obj": NonSerializable()}
    result = safe_json_serialize(data_with_nonserializable)
    assert "non-serializable" in result.lower()

def test_trace_id_formatting():
    """Test trace ID formatting."""
    trace_id = 123456789
    formatted = format_trace_id(trace_id)
    assert len(formatted) == 32
    assert all(c in '0123456789abcdef' for c in formatted)

def test_span_id_formatting():
    """Test span ID formatting."""
    span_id = 123456789
    formatted = format_span_id(span_id)
    assert len(formatted) == 16
    assert all(c in '0123456789abcdef' for c in formatted)

def test_key_sanitization():
    """Test attribute key sanitization."""
    assert sanitize_key("normal_key") == "normal_key"
    assert sanitize_key("123key") == "_123key"
    assert sanitize_key("special!@#key") == "special___key"

def test_string_truncation():
    """Test string truncation functionality."""
    long_string = "a" * 2000
    truncated = truncate_string(long_string, max_length=1000)
    assert len(truncated) == 1000
    assert truncated.endswith("...")

    # Test string shorter than max length
    short_string = "Hello, world!"
    assert truncate_string(short_string, max_length=1000) == short_string

class TestMetricsHelper:
    """Test the MetricsHelper class methods."""
    
    def test_calculate_rate(self):
        """Test rate calculation."""
        assert MetricsHelper.calculate_rate(100, 10) == 10.0
        assert MetricsHelper.calculate_rate(100, 0) == 0.0
    
    def test_format_duration(self):
        """Test duration formatting."""
        assert MetricsHelper.format_duration(0.5) == "500.00ms"
        assert MetricsHelper.format_duration(5) == "5.00s"
        assert MetricsHelper.format_duration(65) == "1m 5.00s"
    
    def test_calculate_percentile(self):
        """Test percentile calculation."""
        values = [1, 2, 3, 4, 5]
        assert MetricsHelper.calculate_percentile(values, 50) == 3.0
        assert MetricsHelper.calculate_percentile([], 50) == 0.0

def test_token_counting():
    """Test token counting functions."""
    # Test prompt token counting
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"}
    ]
    prompt_tokens = count_prompt_tokens(messages, "gpt-3.5-turbo")
    assert prompt_tokens > 0
    
    # Test text token counting
    text = "Hello, world!"
    text_tokens = count_text_tokens(text, "gpt-3.5-turbo")
    assert text_tokens > 0

def test_response_serialization():
    """Test response serialization functions."""
    # Mock response objects
    class MockChoice:
        def __init__(self, text=None, message=None):
            self.text = text
            self.message = message
            self.index = 0
            self.finish_reason = "stop"
    
    class MockUsage:
        def __init__(self):
            self.prompt_tokens = 10
            self.completion_tokens = 20
            self.total_tokens = 30
    
    class MockMessage:
        def __init__(self):
            self.role = "assistant"
            self.content = "Hello"
    
    class MockChatCompletion:
        def __init__(self):
            self.id = "test_id"
            message = MockMessage()
            self.choices = [MockChoice(message=message)]
            self.model = "gpt-3.5-turbo"
            self.usage = MockUsage()
    
    class MockCompletion:
        def __init__(self):
            self.id = "test_id"
            self.choices = [MockChoice(text="Hello")]
            self.model = "text-davinci-003"
            self.usage = MockUsage()
    
    # Test chat completion serialization
    chat_completion = MockChatCompletion()
    serialized_chat = serialize_chat_completion(chat_completion)
    assert serialized_chat["id"] == "test_id"
    assert serialized_chat["choices"][0]["message"]["content"] == "Hello"
    
    # Test completion serialization
    completion = MockCompletion()
    serialized = serialize_completion(completion)
    assert serialized["id"] == "test_id"
    assert serialized["choices"][0]["text"] == "Hello"
    
    # Test generic response serialization
    assert isinstance(serialize_llm_response(completion), dict)
    assert isinstance(serialize_llm_response(chat_completion), dict)
    assert isinstance(serialize_llm_response({"key": "value"}), dict)