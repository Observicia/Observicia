import pytest
from unittest.mock import Mock, AsyncMock
import ollama
from observicia.core.token_tracker import TokenTracker
from observicia.core.context_manager import ObservabilityContext, ContextManager
from observicia.patchers.ollama import OllamaPatcher


@pytest.fixture(autouse=True)
def setup_observability_context():
    """Initialize ObservabilityContext before each test."""
    ObservabilityContext._instance = None
    ObservabilityContext.initialize(service_name="test-service")
    yield
    ObservabilityContext._instance = None


@pytest.fixture
def token_tracker():
    return TokenTracker()


@pytest.fixture
def mock_context(setup_observability_context):
    context = ContextManager(service_name="test-service")
    context.policy_engine = None
    return context


@pytest.fixture
def patcher(token_tracker, mock_context):
    return OllamaPatcher(token_tracker=token_tracker, context=mock_context)


def create_mock_response(content: str, is_chat: bool = False):
    """Helper to create mock responses in Ollama format"""
    if is_chat:
        return {
            'model': 'llama2',
            'message': {
                'role': 'assistant',
                'content': content,
            },
        }
    return {
        'model': 'llama2',
        'response': content,
    }


def test_patcher_initialization(patcher):
    """Test basic patcher initialization."""
    assert isinstance(patcher._token_tracker, TokenTracker)
    assert len(patcher._original_functions) == 0
    assert not patcher._patched


def test_patch_and_unpatch(patcher):
    """Test patching and unpatching the Ollama SDK."""
    original_functions = patcher.patch()
    assert patcher._patched
    assert len(original_functions
               ) == 9  # 3 module-level + 3 sync client + 3 async client

    patcher.unpatch()
    assert not patcher._patched
    assert len(patcher._original_functions) == 0


def test_sync_generate(patcher, monkeypatch):
    """Test synchronous generate wrapping."""
    mock_generate = Mock(return_value=create_mock_response("Test response"))
    monkeypatch.setattr(ollama, 'generate', mock_generate)

    with patcher:
        response = ollama.generate(model='llama2', prompt='Test prompt')

    assert response['response'] == "Test response"
    mock_generate.assert_called_once()


def test_sync_chat(patcher, monkeypatch):
    """Test synchronous chat wrapping."""
    mock_chat = Mock(
        return_value=create_mock_response("Test response", is_chat=True))
    monkeypatch.setattr(ollama, 'chat', mock_chat)

    messages = [{'role': 'user', 'content': 'Test message'}]
    with patcher:
        response = ollama.chat(model='llama2', messages=messages)

    assert response['message']['content'] == "Test response"
    mock_chat.assert_called_once()


def test_sync_generate_with_client(patcher, monkeypatch):
    """Test synchronous generate with client."""
    mock_generate = Mock(return_value=create_mock_response("Test response"))
    monkeypatch.setattr(ollama.Client, 'generate', mock_generate)

    with patcher:
        client = ollama.Client()
        response = client.generate(model='llama2', prompt='Test prompt')

    assert response['response'] == "Test response"
    mock_generate.assert_called_once()


@pytest.mark.asyncio
async def test_async_generate_with_client(patcher, monkeypatch):
    """Test asynchronous generate with client."""
    mock_generate = AsyncMock(
        return_value=create_mock_response("Test response"))
    monkeypatch.setattr(ollama.AsyncClient, 'generate', mock_generate)

    with patcher:
        client = ollama.AsyncClient()
        response = await client.generate(model='llama2', prompt='Test prompt')

    assert response['response'] == "Test response"
    mock_generate.assert_called_once()


def test_sync_embed(patcher, monkeypatch):
    """Test synchronous embed wrapping."""
    mock_response = {
        'model': 'llama2',
        'embeddings': [[0.1, 0.2, 0.3]],
    }
    mock_embed = Mock(return_value=mock_response)
    monkeypatch.setattr(ollama.Client, 'embed', mock_embed)

    with patcher:
        client = ollama.Client()
        response = client.embed(model='llama2', input='Test input')

    assert response['embeddings'] == [[0.1, 0.2, 0.3]]
    mock_embed.assert_called_once()


@pytest.mark.asyncio
async def test_async_embed(patcher, monkeypatch):
    """Test asynchronous embed wrapping."""
    mock_response = {
        'model': 'llama2',
        'embeddings': [[0.1, 0.2, 0.3]],
    }
    mock_embed = AsyncMock(return_value=mock_response)
    monkeypatch.setattr(ollama.AsyncClient, 'embed', mock_embed)

    with patcher:
        client = ollama.AsyncClient()
        response = await client.embed(model='llama2', input='Test input')

    assert response['embeddings'] == [[0.1, 0.2, 0.3]]
    mock_embed.assert_called_once()


def test_error_handling(patcher, monkeypatch):
    """Test error handling in wrapped functions."""
    mock_generate = Mock(side_effect=ValueError("Test error"))
    monkeypatch.setattr(ollama, 'generate', mock_generate)

    with patcher:
        with pytest.raises(ValueError, match="Test error"):
            ollama.generate(model='llama2', prompt='Test prompt')


@pytest.mark.asyncio
async def test_async_error_handling(patcher, monkeypatch):
    """Test error handling in async wrapped functions."""
    mock_generate = AsyncMock(side_effect=ValueError("Test error"))
    monkeypatch.setattr(ollama.AsyncClient, 'generate', mock_generate)

    with patcher:
        client = ollama.AsyncClient()
        with pytest.raises(ValueError, match="Test error"):
            await client.generate(model='llama2', prompt='Test prompt')


def test_token_tracking(patcher, monkeypatch):
    """Test token tracking functionality."""
    mock_generate = Mock(return_value=create_mock_response("Test response"))
    monkeypatch.setattr(ollama, 'generate', mock_generate)

    with patcher:
        response = ollama.generate(model='llama2', prompt='Test prompt')

    # Check if tokens were tracked
    usage = patcher._token_tracker.get_usage('ollama')
    assert usage['prompt_tokens'] > 0
    assert usage['completion_tokens'] > 0
    assert usage['total_tokens'] > 0


@pytest.mark.asyncio
async def test_async_token_tracking(patcher, monkeypatch):
    """Test token tracking in async operations."""
    mock_generate = AsyncMock(
        return_value=create_mock_response("Test response"))
    monkeypatch.setattr(ollama.AsyncClient, 'generate', mock_generate)

    with patcher:
        client = ollama.AsyncClient()
        response = await client.generate(model='llama2', prompt='Test prompt')

    # Check if tokens were tracked
    usage = patcher._token_tracker.get_usage('ollama')
    assert usage['prompt_tokens'] > 0
    assert usage['completion_tokens'] > 0
    assert usage['total_tokens'] > 0
