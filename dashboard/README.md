# LLM Token Usage Dashboard

This project provides tools to visualize LLM token usage metrics from Observicia telemetry logs using Grafana.

![Token Usage Dashboard](Observicia-sqlite-dashboard.webm)

## Overview

The solution consists of two parts:
1. A SQLite database storing Observicia telemetry data
2. A Grafana dashboard configuration that visualizes the token usage metrics

## Prerequisites

- Python 3.8+
- Grafana 9.0+
- Grafana SQLite plugin

## Step 1: Set Up SQLite Database

Use SQLite as Observicia telemetry data store:

```yaml
service_name: langchain-app
otel_endpoint: null
opa_endpoint: http://opa-server:8181/
policies:
logging:
  file: "observicia.log"
  sqlite:
    enabled: true
    database: "observicia.db"
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


## Step 2: Set Up Grafana

1. Install SQLite plugin:
   - Navigate to Configuration > Plugins
   - Search for "SQLite"
   - Install the SQLite plugin

2. Add SQLite datasource:
   - Go to Configuration > Data Sources
   - Click "Add data source"
   - Search for and select "SQLite"
   - Configure the path to your SQLite database
   - Click "Save & Test"

3. Create the dashboard:
   - Click the "+" icon in the sidebar
   - Select "Import"
   - Paste the provided dashboard JSON
   - Select your SQLite datasource
   - Click "Import"

## Dashboard Features

The dashboard includes:

1. **Token Usage Over Time**
   - Line chart showing prompt and completion tokens
   - Includes mean and sum calculations

2. **Token Usage by Model**
   - Pie chart breakdown by model
   - Shows percentages and absolute values

3. **Average Request Duration**
   - Gauge showing mean request duration
   - Color-coded thresholds

4. **Request Details**
   - Detailed table view of all requests
   - Sortable columns
   - Pagination support

5. **Per-User Analytics**
   - Total token usage per user
   - Time series of user token consumption
   - Daily usage patterns
   - Cumulative token usage tracking
   - User comparison metrics

The per-user views allow you to:
- Track individual user consumption patterns
- Compare usage across different users
- Monitor daily and cumulative token usage
- Analyze usage trends over time

---
*This example is part of the [Observicia SDK](https://github.com/observicia/observicia) documentation.*