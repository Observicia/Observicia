"""
LLM SDK patchers for various providers.
"""

from .openai import OpenAIPatcher
from .anthropic import AnthropicPatcher
from .litellm import LiteLLMPatcher
from .watsonx import WatsonxPatcher

DEFAULT_PATCHERS = {
    "openai": OpenAIPatcher,
    "anthropic": AnthropicPatcher,
    "litellm": LiteLLMPatcher,
    "watsonx": WatsonxPatcher
}

__all__ = [
    "OpenAIPatcher", "AnthropicPatcher", "LiteLLMPatcher", "WatsonxPatcher",
    "DEFAULT_PATCHERS"
]
