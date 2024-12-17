# Ollama Generation Example

## Overview
This example illustrates integration with Ollama for local model deployment, including generation, chat, and embedding capabilities with comprehensive monitoring.

## Learning Objectives
- Integrate Observicia SDK with Ollama
- Monitor local model deployments
- Track token usage for local models

## Key Features Demonstrated
1. **Ollama Integration**
   - Local model setup
   - Generation and chat modes
   - Embedding tracking

2. **Observability Features**
   - Token usage monitoring
   - Generation metrics
   - Model performance tracking

## Prerequisites
- Python 3.8 or higher
- Ollama installed locally
- Local models pulled via Ollama

## Installation

1. Install dependencies:
```bash
pip install observicia ollama
```

2. Pull required models:
```bash
ollama pull llama2
```

## Configuration

The example uses `observicia_config.yaml`:
```yaml
service_name: ollama-app
otel_endpoint: null
opa_endpoint: http://opa-server:8181/
logging:
  file: "ollama-app.json"
  telemetry:
    enabled: true
    format: "json"
  messages:
    enabled: true
    level: "INFO"
```

## Running the Example

Basic usage:
```bash
python app.py
```

Available options:
- `--host`: Ollama server address
- `--model`: Model to use (default: llama2)
- `--mode`: Operation mode (generate/chat)

## Code Structure

```
ollama-generate/
├── app.py                    # Main Ollama integration
├── observicia_config.yaml    # SDK configuration
└── README.md                # This file
```

---
*This example is part of the [Observicia SDK](https://github.com/observicia/observicia) documentation.*