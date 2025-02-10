from observicia import init
from observicia.core.context_manager import ObservabilityContext

# Initialize Observicia
init()

# Set user ID for tracking
ObservabilityContext.set_user_id("johndoe")

import os
from typing import List, Optional
from ibm_watsonx_ai.foundation_models import ModelInference
from ibm_watsonx_ai import Credentials
from ibm_watsonx_ai.foundation_models.utils.enums import ModelTypes


class WatsonxBackend:
    """Simplified watsonx backend for testing the patcher"""

    def __init__(self):
        # Get credentials from environment
        self.api_key = os.getenv("WATSONX_KEY")
        self.project_id = os.getenv("WATSONX_PROJECT_ID")
        self.url = os.getenv("WATSONX_URL",
                             "https://us-south.ml.cloud.ibm.com")

        if not self.api_key or not self.project_id:
            raise ValueError("WATSONX_KEY and WATSONX_PROJECT_ID must be set")

        # Initialize credentials
        self.credentials = Credentials(api_key=self.api_key, url=self.url)

        # Initialize model
        self.model = ModelInference(
            model_id=ModelTypes.MIXTRAL_8X7B_INSTRUCT_V01,
            credentials=self.credentials,
            project_id=self.project_id,
            params={
                "temperature": 0.7,
                "top_p": 1
            })

    def generate(self, prompt: str) -> str:
        """Generate text using watsonx model"""
        response = self.model.generate_text(prompt)
        return response

    def generate_with_details(self, prompt: str) -> dict:
        """Generate text and return full response details"""
        return self.model.generate(prompt)

    def chat(self, messages: List[dict]) -> dict:
        """Use chat interface if supported by model"""
        return self.model.chat(messages)
    
    def chat_stream(self, messages: List[dict]) -> Optional[dict]:
        """Use chat interface with streaming if supported by model"""
        return self.model.chat_stream(messages)


def test_chat():
    # Initialize backend
    backend = WatsonxBackend()
    # Test chat if supported
    print("\nTesting chat:")
    messages = [
        {
            "role": "user",
            "content": "Tell me a short story about a robot."
        },
        {
            "role": "assistant",
            "content": "You are a helpful assistant."
        },
    ]

    response = backend.chat(messages)
    print(response)
    # Test chat with streaming if supported
    print("\nTesting chat with streaming:")
    response = backend.chat_stream(messages)
    print(response)


if __name__ == "__main__":
    test_chat()
