from observicia import init
from observicia.core.context_manager import ObservabilityContext

# Initialize Observicia
init()

# Set user ID for tracking
ObservabilityContext.set_user_id("johndoe")

from ollama import Client
import sys
import argparse


def generate_with_ollama(prompt,
                         model="llama2",
                         system_prompt=None,
                         max_tokens=100,
                         host="http://localhost:11434"):
    """
    Generate text using Ollama's Python client.
    
    Args:
        prompt (str): The input prompt for generation
        model (str): The model to use for generation (default: "llama2")
        system_prompt (str, optional): System prompt to set context
        max_tokens (int): Maximum number of tokens to generate
        host (str): Ollama server address (default: "http://localhost:11434")
    
    Returns:
        str: The generated text response
    """
    try:
        # Initialize Ollama client with custom host if provided
        client = Client(host=host)

        # Prepare generation options
        options = {
            "num_predict": max_tokens,
        }

        # Generate response
        response = client.generate(
            model=model,
            prompt=prompt,
            system=system_prompt if system_prompt else "",
            options=options)

        return response

    except Exception as e:
        print(f"Error generating response: {e}", file=sys.stderr)
        return None


def chat_with_ollama(messages, model="llama2", host="http://localhost:11434"):
    """
    Have a conversation using Ollama's chat API.
    
    Args:
        messages (list): List of message dictionaries with 'role' and 'content'
        model (str): The model to use for chat
        host (str): Ollama server address
    
    Returns:
        dict: The chat response
    """
    try:
        client = Client(host=host)
        response = client.chat(model=model, messages=messages)
        return response

    except Exception as e:
        print(f"Error in chat: {e}", file=sys.stderr)
        return None


def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Ollama API Client')
    parser.add_argument(
        '--host',
        default='http://localhost:11434',
        help='Ollama server address (default: http://localhost:11434)')
    parser.add_argument('--model',
                        default='llama2',
                        help='Model to use (default: llama2)')
    parser.add_argument(
        '--mode',
        choices=['generate', 'chat'],
        default='generate',
        help='Operation mode: generate or chat (default: generate)')
    args = parser.parse_args()

    # Example prompts
    if args.mode == 'generate':
        prompt = "Write a short poem about coding"
        system_prompt = "You are a helpful AI assistant that writes creative poetry."

        print(f"\nGenerating text using {args.model} on {args.host}...")
        result = generate_with_ollama(prompt=prompt,
                                      system_prompt=system_prompt,
                                      model=args.model,
                                      max_tokens=100,
                                      host=args.host)

        if result:
            print("\nGenerated text:")
            print(result['response'])

    else:  # chat mode
        messages = [{
            "role":
            "user",
            "content":
            "Hello! Can you help me with Python programming?"
        }]

        print(f"\nStarting chat using {args.model} on {args.host}...")
        chat_response = chat_with_ollama(messages=messages,
                                         model=args.model,
                                         host=args.host)

        if chat_response:
            print("\nChat response:")
            print(chat_response['message']['content'])


if __name__ == "__main__":
    main()
