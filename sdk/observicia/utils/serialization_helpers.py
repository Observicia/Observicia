"""Helpers for serializing API responses."""
from typing import Any, Dict
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.completion import Completion


def serialize_chat_completion(response: ChatCompletion) -> Dict[str, Any]:
    """Convert ChatCompletion to a JSON-serializable dict."""
    return {
        "id":
        response.id,
        "choices": [{
            "index": choice.index,
            "message": {
                "role": choice.message.role,
                "content": choice.message.content
            } if choice.message else {},
            "finish_reason": choice.finish_reason
        } for choice in response.choices],
        "model":
        response.model,
        "usage": {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        } if response.usage else {}
    }


def serialize_completion(response: Completion) -> Dict[str, Any]:
    """Convert Completion to a JSON-serializable dict."""
    return {
        "id":
        response.id,
        "choices": [{
            "text": choice.text,
            "index": choice.index,
            "finish_reason": choice.finish_reason
        } for choice in response.choices],
        "model":
        response.model,
        "usage": {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        } if response.usage else {}
    }


def serialize_llm_response(response: Any) -> Dict[str, Any]:
    """Serialize any LLM response to a JSON-serializable format."""
    if isinstance(response, ChatCompletion):
        return serialize_chat_completion(response)
    elif isinstance(response, Completion):
        return serialize_completion(response)
    elif isinstance(response, dict):
        return response
    else:
        # For unknown types, try to convert to dict if possible
        try:
            return dict(response)
        except (TypeError, ValueError):
            return {"content": str(response)}
