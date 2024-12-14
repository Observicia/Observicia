import warnings

warnings.filterwarnings("ignore", category=UserWarning)

from observicia import init
from observicia.core.context_manager import ObservabilityContext

# Initialize Observicia
init()

# Set user ID for tracking
ObservabilityContext.set_user_id("johndoe")

from langchain.llms import OpenAI
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain

# Initialize OpenAI language model
llm = OpenAI(temperature=0.7)

# Initialize conversation memory
memory = ConversationBufferMemory()

# Create conversation chain
conversation = ConversationChain(llm=llm, memory=memory)

# Sample prompts for multi-round chat
sample_prompts = [
    "Hello! How are you today?", "What's the weather like in New York?",
    "Tell me a joke!", "What's the capital of France?",
    "Who is the current President of the United States?",
    "What's your favorite color?", "What's the meaning of life?",
    "What's the best programming language?", "What's your favorite movie?",
    "What's your favorite book?", "What's your favorite food?",
    "What's your favorite animal?", "What's your favorite song?",
    "What's your favorite sport?", "What's your favorite hobby?",
    "What's your favorite TV show?", "What's your favorite video game?",
    "What's your favorite place to visit?", "What's your favorite season?",
    "Goodbye!"
]


def main():
    """Run the conversation with sample prompts."""
    print("Starting multi-round chat...")

    # Start a chat conversation
    transaction_id = ObservabilityContext.start_transaction(
        metadata={"conversation_type": "multi-round-chat"})

    for prompt in sample_prompts:
        print(f"User: {prompt}")
        response = conversation.run(prompt)
        print(f"AI: {response}\n")

    ObservabilityContext.end_transaction(transaction_id,
                                         metadata={"resolution": "completed"})


if __name__ == "__main__":
    main()
