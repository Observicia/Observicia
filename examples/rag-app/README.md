# Patient RAG Application Example

## Overview
A privacy-aware Retrieval Augmented Generation (RAG) system to illustrate how to handle sensitive patient data with built-in PII protection and policy enforcement using Observicia SDK. 
This example shows how to build secure and observable RAG applications with automatic policy enforcement and chat performance monitoring.

## Learning Objectives
- Build secure RAG systems with PII protection
- Handle sensitive information securely

## Key Features Demonstrated
1. **Privacy Protection**
   - Automated PII detection
   - Policy-based access control

2. **RAG System Components**
   - Vector similarity search (FAISS)

3. **Observability Features**
   - Retrieval accuracy monitoring
   - Token usage optimization
   - Response relevance tracking
   - Policy enforcement logging

## Prerequisites
- Python 3.8 or higher
- OpenAI API key

## Installation

1. Install dependencies:
```bash
pip install observicia openai faiss-cpu sentence-transformers
```

2. Set required environment variables:
```bash
export OPENAI_API_KEY='your-api-key'
```

## Configuration

The example uses `observicia_config.yaml`:
```yaml
service_name: patient-rag-app
otel_endpoint: null
opa_endpoint: http://opa-server:8181/
policies:
  - name: pii_check
    path: policies/pii
    description: Check for PII in responses
    required_trace_level: enhanced
    risk_level: high
  - name: prompt_compliance
    path: policies/prompt_compliance
    description: Check for prompt compliance
    required_trace_level: basic
    risk_level: medium
```

## Running the Example

Basic usage:
```bash
python app.py
```

Available options:
- `--similarity-threshold FLOAT`: Set minimum similarity score (0-1)
- `--max-docs INT`: Maximum number of documents to retrieve

## Code Structure

```
rag-app/
├── app.py                    # Main RAG implementation
├── observicia_config.yaml    # SDK and policy configuration
└── README.md                # This file
```


## Generated Artifacts
The example generates:
- `rag-app.json`: Telemetry data for system performance
- `rag-chat.json`: Interaction history with policy checks


## Common Issues and Solutions
- **Issue**: Low retrieval relevance
  - **Solution**: Adjust similarity threshold or increase document count

- **Issue**: PII detection false positives
  - **Solution**: Fine-tune PII policies in configuration

## Additional Resources
- [Observicia SDK Documentation](https://observicia.readthedocs.io/)


---
*This example is part of the [Observicia SDK](https://github.com/observicia/observicia) documentation.*