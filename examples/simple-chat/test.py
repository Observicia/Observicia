import asyncio
import os
from typing import List
from observicia import init

# Initialize Observicia
init("openai-test-suite", trace_console=True)

from openai import AsyncOpenAI, OpenAI
from openai.types import FileObject
from pathlib import Path


class OpenAITester:

    def __init__(self):
        self.async_client = AsyncOpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"))
        self.sync_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    async def test_async_chat_completion(self):
        """Test async chat completions with and without streaming"""
        print("\n=== Testing Async Chat Completion ===")

        # Test without streaming
        response = await self.async_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": "Say hello!"
            }],
            temperature=0.7,
        )
        print(f"Non-streaming response: {response.choices[0].message.content}")

        # Test with streaming
        print("\nStreaming response: ", end="", flush=True)
        stream = await self.async_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": "Count from 1 to 5"
            }],
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                print(chunk.choices[0].delta.content, end="", flush=True)
        print()

    def test_sync_completion(self):
        """Test synchronous text completions"""
        print("\n=== Testing Sync Text Completion ===")

        # Test without streaming
        response = self.sync_client.completions.create(
            model="gpt-3.5-turbo-instruct",
            prompt="Write a haiku about coding",
            max_tokens=50)
        print(f"Non-streaming response: {response.choices[0].text}")

        # Test with streaming
        print("\nStreaming response: ", end="", flush=True)
        stream = self.sync_client.completions.create(
            model="gpt-3.5-turbo-instruct",
            prompt="Write a limerick about Python",
            max_tokens=50,
            stream=True)
        for chunk in stream:
            if chunk.choices[0].text:
                print(chunk.choices[0].text, end="", flush=True)
        print()

    async def test_embeddings(self):
        """Test embedding generation"""
        print("\n=== Testing Embeddings ===")

        texts = ["Hello world", "How are you?", "Testing embeddings"]

        # Async embeddings
        async_response = await self.async_client.embeddings.create(
            model="text-embedding-ada-002",
            input=texts,
        )
        print(
            f"Generated {len(async_response.data)} embeddings of dimension {len(async_response.data[0].embedding)}"
        )

        # Sync embeddings
        sync_response = self.sync_client.embeddings.create(
            model="text-embedding-ada-002",
            input="Single text embedding test",
        )
        print(
            f"Single embedding dimension: {len(sync_response.data[0].embedding)}"
        )

    async def test_image_generation(self):
        """Test image generation and variation"""
        print("\n=== Testing Image Generation ===")

        # Generate image
        response = await self.async_client.images.generate(
            model="dall-e-2",
            prompt="A cute robot learning to code",
            n=1,
            size="256x256")
        print(f"Generated image URL: {response.data[0].url}")

    async def test_file_operations(self):
        """Test file upload, list, and deletion"""
        print("\n=== Testing File Operations ===")

        # Create a test file
        with open("test_file.jsonl", "w") as f:
            f.write('{"prompt": "Hello", "completion": "Hi there!"}\n')
            f.write('{"prompt": "How are you?", "completion": "I am good!"}\n')

        # Upload file
        with open("test_file.jsonl", "rb") as f:
            file: FileObject = await self.async_client.files.create(
                file=f, purpose="fine-tune")
        print(f"Uploaded file ID: {file.id}")

        # List files
        files = await self.async_client.files.list()
        print(f"Number of files: {len(files.data)}")

        # Delete file
        deletion = await self.async_client.files.delete(file.id)
        print(f"File deleted: {deletion.deleted}")

        # Clean up
        os.remove("test_file.jsonl")

    async def test_moderations(self):
        """Test content moderation"""
        print("\n=== Testing Content Moderation ===")

        texts = [
            "Hello, how are you?",
            "I love programming!",
        ]

        response = await self.async_client.moderations.create(
            input=texts, model="text-moderation-latest")

        for i, result in enumerate(response.results):
            print(f"Text {i + 1} flagged: {result.flagged}")

    async def run_all_tests(self):
        """Run all test cases"""
        try:
            # Async tests
            await self.test_async_chat_completion()
            await self.test_embeddings()
            await self.test_image_generation()
            await self.test_file_operations()
            await self.test_moderations()

            # Sync tests
            self.test_sync_completion()

            print("\n=== All tests completed successfully ===")

        except Exception as e:
            print(f"\nError during testing: {str(e)}")


async def main():
    tester = OpenAITester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
