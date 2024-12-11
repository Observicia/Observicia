"""
Observicia - Policy-Aware Tracing SDK for LLM Applications
"""

from observicia.core.context_manager import ObservabilityContext
from observicia.core.policy_engine import PolicyEngine, PolicyResult
from observicia.core.tracing_manager import TracingClient
from observicia.core.token_tracker import TokenTracker
from observicia.core.patch_manager import PatchManager
from observicia.core.policy_engine import Policy
from typing import List, Optional
import os
import yaml

__version__ = "0.1.4"


def init() -> None:
    """Initialize the Observicia SDK.
    """
    # Get the config file path from an environment variable
    config_file = os.environ.get("OBSERVICIA_CONFIG_FILE",
                                 "observicia_config.yaml")

    # Load configurations
    try:
        with open(config_file, "r") as file:
            config = yaml.safe_load(file)
            # Extract configurations
            service_name = config.get("service_name", "default-service")
            otel_endpoint = config.get("otel_endpoint", None)
            opa_endpoint = config.get("opa_endpoint", None)
            policies = config.get("policies", [])
            log_file = config.get("log_file", None)
            trace_console = config.get("trace_console", False)

            policy_objects = [Policy(**policy)
                              for policy in policies] if policies else None

            ObservabilityContext.initialize(service_name=service_name,
                                            otel_endpoint=otel_endpoint,
                                            opa_endpoint=opa_endpoint,
                                            trace_console=trace_console,
                                            log_file=log_file,
                                            policies=policy_objects)

            # Auto-detect and patch installed providers
            patch_manager = PatchManager()
            patch_manager.patch_all()

    except FileNotFoundError:
        print(f"Configuration file {config_file} not found. Ignoring.")
    except yaml.YAMLError as e:
        print(f"Error parsing the YAML configuration file: {e}. Ignoring.")


# Expose main decorators
from observicia.core.tracing_manager import trace, trace_rag, trace_stream

# Expose utilities
from observicia.utils.helpers import get_current_span, get_current_context

__all__ = [
    "init", "trace", "trace_rag", "trace_stream", "get_current_span",
    "get_current_context", "PolicyResult", "__version__"
]
