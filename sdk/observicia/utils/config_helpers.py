import os
from typing import Dict, Any, Optional

def get_env_value(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get value from environment variable.
    Supports both direct values and references to other env vars.
    
    Example:
        ENV_VAR=value
        ENV_REF=${OTHER_VAR}
    """
    value = os.getenv(key, default)
    if value and value.startswith("${") and value.endswith("}"):
        # It's a reference to another env var
        env_var_name = value[2:-1]  # Remove ${ and }
        return os.getenv(env_var_name, default)
    return value

def process_redis_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process Redis configuration to substitute environment variables
    for sensitive credentials.
    
    Expects config format:
    {
        "enabled": bool,
        "host": str,
        "port": int,
        "db": int,
        "username": str,  # Can be env var reference
        "password": str,  # Can be env var reference
        "key_prefix": str,
        "retention_hours": int
    }
    """
    if not isinstance(config, dict):
        return config

    processed_config = config.copy()
    
    # Handle username
    if "username" in processed_config:
        username = get_env_value("REDIS_USERNAME", processed_config["username"])
        processed_config["username"] = username

    # Handle password
    if "password" in processed_config:
        password = get_env_value("REDIS_PASSWORD", processed_config["password"])
        processed_config["password"] = password
        
    return processed_config