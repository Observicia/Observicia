"""
Observicia - Policy-Aware Tracing SDK for LLM Applications
"""

from observicia.core.context_manager import ObservabilityContext
from observicia.core.policy_engine import PolicyEngine, PolicyResult, Policy
from observicia.core.tracing_manager import TracingClient
from observicia.core.token_tracker import TokenTracker
from observicia.core.patch_manager import PatchManager
from typing import List, Optional, Dict, Any
import os
import yaml

__version__ = "0.1.2"


def init() -> None:
    """Initialize the Observicia SDK."""
    # Get the config file path from an environment variable
    config_file = os.environ.get("OBSERVICIA_CONFIG_FILE",
                                 "observicia_config.yaml")

    # Default logging configuration
    default_logging = {
        "file": None,
        "telemetry": {
            "enabled": False,
            "format": "json"
        },
        "messages": {
            "enabled": False,
            "level": "INFO"
        },
        "chat": {
            "enabled": False,
            "level": "none",
            "file": None
        }
    }

    try:
        with open(config_file, "r") as file:
            config = yaml.safe_load(file)

            # Extract configurations
            service_name = config.get("service_name", "default-service")
            otel_endpoint = config.get("otel_endpoint", None)
            opa_endpoint = config.get("opa_endpoint", None)
            policies = config.get("policies", [])
            logging_config = config.get("logging", default_logging)

            policy_objects = [Policy(**policy)
                              for policy in policies] if policies else None

            ObservabilityContext.initialize(service_name=service_name,
                                            otel_endpoint=otel_endpoint,
                                            opa_endpoint=opa_endpoint,
                                            policies=policy_objects,
                                            logging_config=logging_config)

            # Auto-detect and patch installed providers
            patch_manager = PatchManager()
            patch_manager.patch_all()

    except FileNotFoundError:
        print(f"Configuration file {config_file} not found. Using defaults.")
        ObservabilityContext.initialize(service_name="default-service",
                                        logging_config=default_logging)
    except yaml.YAMLError as e:
        print(
            f"Error parsing the YAML configuration file: {e}. Using defaults.")
        ObservabilityContext.initialize(service_name="default-service",
                                        logging_config=default_logging)


# Expose main decorators
from observicia.core.tracing_manager import trace, trace_rag, trace_stream

# Expose utilities
from observicia.utils.helpers import get_current_span, get_current_context

__all__ = [
    "init", "trace", "trace_rag", "trace_stream", "get_current_span",
    "get_current_context", "PolicyResult", "__version__"
]
