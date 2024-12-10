import pytest
import threading
from datetime import datetime, timedelta
from observicia.core.token_tracker import TokenTracker, TokenUsage


@pytest.fixture
def token_tracker():
    return TokenTracker(retention_period=timedelta(days=1))


def test_token_usage_initialization():
    """Test TokenUsage initialization and defaults."""
    usage = TokenUsage()
    assert usage.prompt_tokens == 0
    assert usage.completion_tokens == 0
    assert usage.total_tokens == 0
    assert isinstance(usage.timestamp, datetime)


def test_token_tracker_update(token_tracker):
    """Test updating token usage for a provider."""
    token_tracker.update("openai", prompt_tokens=10, completion_tokens=20)

    totals = token_tracker.get_totals("openai")
    assert totals.prompt_tokens == 10
    assert totals.completion_tokens == 20
    assert totals.total_tokens == 30


def test_stream_context(token_tracker):
    """Test token tracking in streaming context."""
    with token_tracker.stream_context("openai", "test_session") as usage:
        usage.prompt_tokens += 5
        usage.completion_tokens += 10

    totals = token_tracker.get_totals("openai")
    assert totals.prompt_tokens == 5
    assert totals.completion_tokens == 10


def test_stream_context_error_handling(token_tracker):
    """Test stream context handling when errors occur."""
    session_id = "test_session"

    try:
        with token_tracker.stream_context("openai", session_id) as usage:
            usage.prompt_tokens += 5
            usage.completion_tokens += 10
            raise ValueError("Test error")
    except ValueError:
        pass

    with token_tracker._lock:
        assert session_id not in token_tracker._stream_usage

    totals = token_tracker.get_totals("openai")
    assert totals.prompt_tokens == 5
    assert totals.completion_tokens == 10


def test_multi_provider(token_tracker):
    """Test tracking tokens for multiple providers."""
    token_tracker.update("openai", 10, 20)
    token_tracker.update("anthropic", 15, 25)
    token_tracker.update("openai", 5, 10)

    openai_totals = token_tracker.get_totals("openai")
    assert openai_totals.prompt_tokens == 15
    assert openai_totals.completion_tokens == 30

    anthropic_totals = token_tracker.get_totals("anthropic")
    assert anthropic_totals.prompt_tokens == 15
    assert anthropic_totals.completion_tokens == 25


def test_concurrent_updates(token_tracker):
    """Test thread safety with concurrent updates."""

    def update_tokens():
        for _ in range(100):
            token_tracker.update("openai", 1, 2)

    threads = []
    for _ in range(10):
        thread = threading.Thread(target=update_tokens)
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

    totals = token_tracker.get_totals("openai")
    assert totals.prompt_tokens == 1000  # 10 threads * 100 updates * 1 token
    assert totals.completion_tokens == 2000  # 10 threads * 100 updates * 2 tokens


def test_retention_cleanup(token_tracker):
    """Test cleanup of old usage data."""
    old_usage = TokenUsage(prompt_tokens=10, completion_tokens=20)
    old_usage.timestamp = datetime.utcnow() - timedelta(days=2)

    with token_tracker._lock:
        token_tracker._usage_by_provider["test"].append(old_usage)

    token_tracker.update("test", 5, 10)  # This should trigger cleanup

    totals = token_tracker.get_totals("test")
    assert totals.prompt_tokens == 5  # Only recent usage remains
    assert totals.completion_tokens == 10


if __name__ == '__main__':
    pytest.main([__file__])
