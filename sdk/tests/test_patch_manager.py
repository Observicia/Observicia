import pytest
from unittest.mock import Mock, patch, MagicMock
from observicia.core.patch_manager import PatchManager
from observicia.core.context_manager import ObservabilityContext
from observicia.core.token_tracker import TokenTracker


class MockPatcher:
    """Mock patcher class for testing."""

    def __init__(self, token_tracker=None, context=None):
        self.token_tracker = token_tracker
        self.context = context
        self.patched = False
        self.unpatched = False

    def patch(self):
        self.patched = True
        return {"original_func": lambda: None}

    def unpatch(self, original_funcs=None):  # Made original_funcs optional
        self.unpatched = True


@pytest.fixture(autouse=True)
def mock_observability_context():
    """Fixture to mock and initialize ObservabilityContext for all tests."""
    mock_context = Mock(spec=ObservabilityContext)
    mock_instance = Mock()
    mock_context._instance = mock_instance

    with patch(
            'observicia.core.patch_manager.ObservabilityContext') as mock_ctx:
        mock_ctx.get_current.return_value = mock_instance
        yield mock_ctx


@pytest.fixture
def token_tracker():
    return Mock(spec=TokenTracker)


@pytest.fixture
def patch_manager(token_tracker):
    return PatchManager()


def test_init(patch_manager):
    """Test PatchManager initialization."""
    assert patch_manager._active_patches == {}
    assert patch_manager._original_functions == {}
    assert isinstance(patch_manager._token_tracker, TokenTracker)


@pytest.mark.parametrize("provider_name",
                         ["openai", "anthropic", "litellm", "watsonx"])
def test_patch_provider_success(patch_manager, provider_name):
    """Test successful provider patching."""
    mock_patcher = MockPatcher()

    with patch('observicia.core.patch_manager.DEFAULT_PATCHERS',
               {provider_name: lambda **kwargs: mock_patcher}):
        patch_manager.patch_provider(provider_name)

        assert provider_name in patch_manager._active_patches
        assert provider_name in patch_manager._original_functions
        assert mock_patcher.patched


def test_patch_provider_unsupported(mock_observability_context):
    """Test patching an unsupported provider."""
    patch_manager = PatchManager()
    with pytest.raises(ValueError, match="Unsupported provider"):
        patch_manager.patch_provider("unsupported_provider")


def test_patch_provider_import_error(mock_observability_context):
    """Test handling of import errors during patching."""
    patch_manager = PatchManager()

    def mock_patcher(*args, **kwargs):
        raise ImportError("SDK not installed")

    with patch('observicia.core.patch_manager.DEFAULT_PATCHERS',
               {"test": mock_patcher}):
        with pytest.raises(ImportError, match="SDK not installed"):
            patch_manager.patch_provider("test")


def test_patch_provider_runtime_error(mock_observability_context):
    """Test handling of runtime errors during patching."""
    patch_manager = PatchManager()

    def mock_patcher(*args, **kwargs):
        raise RuntimeError("Patching failed")

    with patch('observicia.core.patch_manager.DEFAULT_PATCHERS',
               {"test": mock_patcher}):
        with pytest.raises(RuntimeError, match="Error patching test"):
            patch_manager.patch_provider("test")


def test_unpatch_provider(patch_manager):
    """Test unpatching a provider."""
    mock_patcher = MockPatcher()
    provider_name = "test"

    # Setup patched state
    patch_manager._active_patches[provider_name] = mock_patcher
    patch_manager._original_functions[provider_name] = {"func": lambda: None}

    patch_manager.unpatch_provider(provider_name)

    assert provider_name not in patch_manager._active_patches
    assert provider_name not in patch_manager._original_functions
    assert mock_patcher.unpatched


def test_unpatch_provider_not_patched(patch_manager):
    """Test unpatching a provider that wasn't patched."""
    patch_manager.unpatch_provider("test")  # Should not raise any exceptions


def test_patch_all(patch_manager):
    """Test patching all providers."""
    mock_patcher = MockPatcher()
    providers = ["openai", "anthropic"]

    with patch(
            'observicia.core.patch_manager.DEFAULT_PATCHERS',
        {provider: lambda **kwargs: mock_patcher
         for provider in providers}):
        patch_manager.patch_all()

        for provider in providers:
            assert provider in patch_manager._active_patches
            assert provider in patch_manager._original_functions


def test_unpatch_all(patch_manager):
    """Test unpatching all providers."""
    mock_patcher = MockPatcher()
    providers = ["openai", "anthropic"]

    # Setup patched state
    for provider in providers:
        patch_manager._active_patches[provider] = mock_patcher
        patch_manager._original_functions[provider] = {"func": lambda: None}

    patch_manager.unpatch_all()

    assert len(patch_manager._active_patches) == 0
    assert len(patch_manager._original_functions) == 0
    assert mock_patcher.unpatched


def test_context_manager(mock_observability_context):
    """Test PatchManager as context manager."""
    mock_patcher = MockPatcher()
    providers = ["openai", "anthropic"]

    with patch(
            'observicia.core.patch_manager.DEFAULT_PATCHERS',
        {provider: lambda **kwargs: mock_patcher
         for provider in providers}):
        with PatchManager() as manager:
            assert all(provider in manager._active_patches
                       for provider in providers)

        # After context exit, should be unpatched
        assert len(manager._active_patches) == 0
        assert len(manager._original_functions) == 0


def test_rollback_patches(patch_manager):
    """Test rollback functionality when patching fails."""
    mock_patcher = MockPatcher()
    provider = "test"

    # Setup initial state
    patch_manager._original_functions[provider] = {"func": lambda: None}
    patch_manager._active_patches[provider] = mock_patcher

    patch_manager._rollback_patches(provider)

    assert provider not in patch_manager._active_patches
    assert provider not in patch_manager._original_functions
    assert mock_patcher.unpatched


@pytest.mark.asyncio
async def test_async_compatibility(mock_observability_context):
    """Test PatchManager compatibility with async code."""
    mock_patcher = MockPatcher()

    with patch('observicia.core.patch_manager.DEFAULT_PATCHERS',
               {"test": lambda **kwargs: mock_patcher}):

        async def async_function():
            with PatchManager() as manager:
                return manager

        manager = await async_function()
        assert isinstance(manager, PatchManager)


def test_double_patch(patch_manager):
    """Test that patching an already patched provider doesn't cause issues."""
    mock_patcher = MockPatcher()
    provider = "test"

    with patch('observicia.core.patch_manager.DEFAULT_PATCHERS',
               {provider: lambda **kwargs: mock_patcher}):
        # Patch twice
        patch_manager.patch_provider(provider)
        patch_manager.patch_provider(provider)

        # Should only be patched once
        assert len(patch_manager._active_patches) == 1
        assert len(patch_manager._original_functions) == 1


def test_unpatch_during_exception(patch_manager):
    """Test that providers are properly unpatched even if an exception occurs."""
    mock_patcher = MockPatcher()
    provider = "test"

    class TestException(Exception):
        pass

    with patch('observicia.core.patch_manager.DEFAULT_PATCHERS',
               {provider: lambda **kwargs: mock_patcher}):
        try:
            with PatchManager() as manager:
                raise TestException("Test exception")
        except TestException:
            pass

        # Should be unpatched despite exception
        assert len(manager._active_patches) == 0
        assert len(manager._original_functions) == 0
