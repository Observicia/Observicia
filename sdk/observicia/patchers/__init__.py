"""
LLM SDK patchers for various providers.
"""

from .openai import OpenAIPatcher
from .anthropic import AnthropicPatcher
from .litellm import LiteLLMPatcher
from .watsonx import WatsonxPatcher
from .ollama import OllamaPatcher

DEFAULT_PATCHERS = {
    "openai": OpenAIPatcher,
    "anthropic": AnthropicPatcher,
    "litellm": LiteLLMPatcher,
    "watsonx": WatsonxPatcher,
    "ollama": OllamaPatcher
}

__all__ = [
    "OpenAIPatcher", "AnthropicPatcher", "LiteLLMPatcher", "WatsonxPatcher",
    "OllamaPatcher", "DEFAULT_PATCHERS"
]
