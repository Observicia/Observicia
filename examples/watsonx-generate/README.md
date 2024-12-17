# WatsonX Generation Example

## Overview
This example demonstrates integration with IBM WatsonX.ai Foundation Models, showcasing model inference, token tracking, and policy enforcement capabilities.

## Learning Objectives
- Integrate Observicia SDK with WatsonX.ai
- Monitor Foundation Model interactions
- Track token usage for WatsonX models

## Key Features Demonstrated
1. **WatsonX Integration**
   - Model inference setup
   - Parameter configuration
   - Chat interface handling

2. **Observability Features**
   - Token usage tracking
   - Generation metrics
   - Parameter monitoring

## Prerequisites
- Python 3.8 or higher
- WatsonX API key
- IBM Cloud project ID

## Installation

1. Install dependencies:
```bash
pip install observicia ibm_watsonx_ai
```

2. Set required environment variables:
```bash
export WATSONX_KEY='your-api-key'
export WATSONX_PROJECT_ID='your-project-id'
```

## Configuration

The example uses `observicia_config.yaml`:
```yaml
service_name: watsonx-app
otel_endpoint: null
opa_endpoint: http://opa-server:8181/
logging:
  file: "watsonx-app.json"
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

## Code Structure

```
watsonx-generate/
├── app.py                    # Main WatsonX integration
├── observicia_config.yaml    # SDK configuration
└── README.md                # This file
```

---
*This example is part of the [Observicia SDK](https://github.com/observicia/observicia) documentation.*