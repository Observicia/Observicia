# LangChain Chat Example

## Overview
This example illustrates monitoring and tracking capabilities for LangChain-based multi-round conversations.

## Learning Objectives
- Integrate Observicia SDK with LangChain applications
- Manage multi-round conversations with transactions
- Implement logging for LangChain interactions

## Key Features Demonstrated
1. **LangChain Integration**
   - Conversation chain setup
   - Memory management
   - LLM configuration

2. **Transaction Management**
   - Session management
   - Transaction marking

3. **Observability Features**
   - Token usage tracking
   - Multi-round conversation tracking
   - Performance metrics

## Prerequisites
- Python 3.8 or higher
- OpenAI API key

## Installation

1. Install dependencies:
```bash
pip install observicia langchain openai
```

2. Set required environment variables:
```bash
export OPENAI_API_KEY='your-api-key'
```

## Configuration

The example uses `observicia_config.yaml`:
```yaml
service_name: langchain-app
otel_endpoint: null
opa_endpoint: http://opa-server:8181/
logging:
  file: "langchain-app.json"
  telemetry:
    enabled: true
    format: "json"
  messages:
    enabled: true
    level: "INFO"
  chat:
    enabled: true
    level: "both"
    file: "langchain-chat.json"
```

## Running the Example

Basic usage:
```bash
python app.py
```

## Code Structure

```
langchain-chat/
├── app.py                    # Main LangChain integration
├── observicia_config.yaml    # SDK configuration
└── README.md                # This file
```

## Key Concepts

### Initializing LangChain with Observicia
Set up LangChain with observability:
```python
from observicia import init
from observicia.core.context_manager import ObservabilityContext
from langchain.llms import OpenAI
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain

# Initialize Observicia
init()

# Set user ID for tracking
ObservabilityContext.set_user_id("johndoe")
```

### Managing Conversation Transactions
Track conversation lifecycle:
```python
def main():
    # Start a chat conversation
    transaction_id = ObservabilityContext.start_transaction(
        metadata={"conversation_type": "multi-round-chat"}
    )

    # Start conversation

    ObservabilityContext.end_transaction(
        transaction_id,
        metadata={"resolution": "completed"}
    )
```

## Generated Artifacts
The example generates:
- `langchain-app.json`: System telemetry and performance data
- `langchain-chat.json`: Detailed chat interaction history



## Additional Resources
- [Observicia SDK Documentation](https://observicia.readthedocs.io/)

---
*This example is part of the [Observicia SDK](https://github.com/observicia/observicia) documentation.*