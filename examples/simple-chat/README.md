# Simple Chat Example

## Overview
A basic chat application illustrating the core Observicia SDK integration with OpenAI's chat completions API. 
This example provides basic instruction for building observable chat applications.

## Learning Objectives
- Understand basic Observicia SDK initialization and configuration
- Learn how to implement observable chat applications
- Learn token tracking and streaming response handling

## Key Features Demonstrated
1. **SDK Integration**
   - Basic SDK initialization
   - Configuration management
   - API integration patterns

2. **Chat Functionality**
   - Synchronous chat completions
   - Asynchronous streaming responses

3. **Observability Features**
   - Real-time token usage tracking
   - Response timing measurements

## Prerequisites
- Python 3.8 or higher
- OpenAI API key

## Installation

1. Install dependencies:
```bash
pip install observicia openai
```

2. Set up your OpenAI API key:
```bash
export OPENAI_API_KEY='your-api-key'
```

## Configuration

The example uses `observicia_config.yaml`:
```yaml
service_name: chatbot-app
otel_endpoint: null
opa_endpoint: null
policies: []
log_file: telemetry.log
trace_console: false
```

## Running the Example

Basic usage:
```bash
python app.py
```

Available options:
- `--test`: Run with predefined test inputs instead of interactive mode

## Code Structure

```
simple-chat/
├── app.py                    # Main chat application
├── observicia_config.yaml   # SDK configuration
└── README.md                # This file
```

## Key Concepts

### SDK Initialization
Initialize the SDK and set up the user context:
```python
from observicia import init
from observicia.core.context_manager import ObservabilityContext

# Initialize SDK
init()

# Set user ID for tracking
ObservabilityContext.set_user_id("johndoe")
```

### Streaming Chat Implementation
Handle streaming responses with proper observability:
```python
async def chat(messages):
    print("\nAssistant: ", end="", flush=True)
    stream = await client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        max_tokens=50,
        stream=True
    )
    
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)
```

## Generated Artifacts
The example generates:
- `telemetry.log`: Contains detailed SDK telemetry data
- Console output: Interactive chat interface

## Learning Outcomes
1. Initialize and configure the Observicia SDK
2. Implement observable chat applications

## Common Issues and Solutions
- **Issue**: SDK not initialized properly
  - **Solution**: Ensure `init()` is called before any SDK usage

- **Issue**: Missing API key
  - **Solution**: Set OPENAI_API_KEY environment variable

---
*This example is part of the [Observicia SDK](https://github.com/observicia/observicia) documentation.*