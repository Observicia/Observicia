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
    "Who is the president of the United States of America?",
    "What's the tallest mountain in the world?", "What's your favorite color?",
    "What's the best movie you've ever seen in your life?",
    "What's the meaning of life?",
    "What's the most interesting fact you know?",
    "What's the most beautiful place you've ever visited?",
    "What's the best book you've ever read?", "Goodbye!"
]


def main():
    """Run the conversation with sample prompts."""
    print("Starting multi-round chat...")
    for prompt in sample_prompts:
        print(f"User: {prompt}")
        response = conversation.run(prompt)
        print(f"AI: {response}\n")


if __name__ == "__main__":
    main()
