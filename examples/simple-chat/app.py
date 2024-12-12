import asyncio
import os
import argparse
from observicia import init
from observicia.core.context_manager import ObservabilityContext

# Initialize Observicia
init()

# Set user ID
ObservabilityContext.set_user_id("johndoe")

from openai import AsyncOpenAI


async def chat(test_mode=False):
    messages = []
    client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    if test_mode:
        # In test mode, use a predefined input
        test_inputs = [
            "Hello! How are you?", "What's the weather like?", "Goodbye!"
        ]
        for user_input in test_inputs:
            print(f"\nYou: {user_input}")
            messages.append({"role": "user", "content": user_input})
            print("\nAssistant: ", end="", flush=True)

            stream = await client.chat.completions.create(model="gpt-4",
                                                          messages=messages,
                                                          max_tokens=50,
                                                          stream=True)

            response = ""
            async for chunk in stream:
                if not chunk.choices or not chunk.choices[0].delta.content:
                    continue
                content = chunk.choices[0].delta.content
                response += content
                print(content, end="", flush=True)
            print()

            # Add assistant's response to message history
            messages.append({"role": "assistant", "content": response})

            # In test mode, we'll limit to 3 exchanges
            if len(messages) >= 6:  # 3 pairs of messages
                break
        return True
    else:
        # Original interactive mode
        print("Chatbot ready. Type 'exit' to quit.")
        while True:
            user_input = input("\nYou: ").strip()
            if user_input.lower() == 'exit':
                break

            messages.append({"role": "user", "content": user_input})
            print("\nAssistant: ", end="", flush=True)

            stream = await client.chat.completions.create(model="gpt-4",
                                                          messages=messages,
                                                          max_tokens=50,
                                                          stream=True)
            async for chunk in stream:
                if not chunk.choices or not chunk.choices[0].delta.content:
                    continue
                print(chunk.choices[0].delta.content, end="")
            print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run chat application')
    parser.add_argument('--test',
                        action='store_true',
                        help='Run in test mode with predefined inputs')
    args = parser.parse_args()

    asyncio.run(chat(test_mode=args.test))
