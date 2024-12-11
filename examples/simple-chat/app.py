import asyncio
import os
from observicia import init
from observicia.core.context_manager import ObservabilityContext

# Initialize Observicia
init()

# Set user ID
ObservabilityContext.set_user_id("johndoe")

from openai import AsyncOpenAI


async def chat():
    messages = []
    print("Chatbot ready. Type 'exit' to quit.")
    client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() == 'exit':
            break

        messages.append({"role": "user", "content": user_input})
        print("\nAssistant: ", end="", flush=True)

        stream = await client.chat.completions.create(model="gpt-4o-mini",
                                                      messages=messages,
                                                      max_tokens=50,
                                                      stream=True)
        async for chunk in stream:
            if not chunk.choices or not chunk.choices[0].delta.content:
                continue
            print(chunk.choices[0].delta.content, end="")
        print()


if __name__ == "__main__":
    asyncio.run(chat())
