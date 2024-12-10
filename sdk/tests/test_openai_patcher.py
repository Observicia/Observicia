import pytest
from unittest.mock import Mock, patch, AsyncMock
from openai.resources.chat.completions import AsyncCompletions as AsyncChatCompletions
from openai.resources.chat.completions import Completions as ChatCompletions
from observicia.patchers.openai import OpenAIPatcher
from observicia.core.token_tracker import TokenTracker
from observicia.core.context_manager import ObservabilityContext


@pytest.fixture(autouse=True)
def setup_observability_context():
    """Initialize ObservabilityContext before each test."""
    ObservabilityContext._instance = None
    ObservabilityContext.initialize(service_name="test-service",
                                    trace_console=True)
    yield
    ObservabilityContext._instance = None


@pytest.fixture
def token_tracker():
    return TokenTracker()


@pytest.fixture
def mock_context(setup_observability_context):
    context = ObservabilityContext.get_current()
    context._service_name = "test-service"
    context.policy_engine = None
    return context


@pytest.fixture
def patcher(token_tracker, mock_context):
    return OpenAIPatcher(token_tracker=token_tracker, context=mock_context)


class TestOpenAIPatcher:

    def test_initialization(self, patcher):
        """Test patcher initialization."""
        assert isinstance(patcher._token_tracker, TokenTracker)
        assert len(patcher._original_functions) == 0
        assert not patcher._patched

    def test_patch_chat_completions(self, patcher):
        """Test patching chat completions."""
        original_chat_create = ChatCompletions.create

        # Apply patches
        patcher.patch()

        # Verify functions are patched
        assert ChatCompletions.create != original_chat_create
        assert patcher._patched

        # Clean up
        patcher.unpatch()
        assert not patcher._patched

    def test_unpatch(self, patcher):
        """Test unpatching functionality."""
        # Store original references
        original_chat_create = ChatCompletions.create
        original_async_chat_create = AsyncChatCompletions.create

        # Apply patches
        orig_funcs = patcher.patch()
        assert patcher._patched

        # Verify functions were patched
        assert ChatCompletions.create is not original_chat_create
        assert AsyncChatCompletions.create is not original_async_chat_create

        # Unpatch
        patcher.unpatch(orig_funcs)

        # Verify unpatching restored original functionality
        assert not patcher._patched
        current_chat_create = ChatCompletions.create
        assert current_chat_create.__name__ == original_chat_create.__name__
        assert current_chat_create.__module__ == original_chat_create.__module__

    def test_context_manager(self, patcher):
        """Test using patcher as context manager."""
        original_chat_create = ChatCompletions.create

        with patcher:
            assert patcher._patched
            assert ChatCompletions.create is not original_chat_create

        assert not patcher._patched
        current_chat_create = ChatCompletions.create
        assert current_chat_create.__name__ == original_chat_create.__name__
        assert current_chat_create.__module__ == original_chat_create.__module__

    def test_double_patch(self, patcher):
        """Test that patching twice doesn't cause issues."""
        original_chat_create = ChatCompletions.create

        # First patch
        patcher.patch()
        patched_func = ChatCompletions.create

        # Second patch
        patcher.patch()
        assert ChatCompletions.create is patched_func

        # Cleanup
        patcher.unpatch()
        current_chat_create = ChatCompletions.create
        assert current_chat_create.__name__ == original_chat_create.__name__
        assert current_chat_create.__module__ == original_chat_create.__module__


if __name__ == '__main__':
    pytest.main([__file__])
