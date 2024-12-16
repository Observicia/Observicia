# Base template that all policies should extend
package observicia.base

# Default result structure
default result = {
    "allow": false,
    "violations": [],
    "risk_level": "low",
    "trace_level": "basic",
    "metadata": {}
}

# Base allow rule that policies should override
default allow = false

# Base violation rule that policies should override
violations[msg] {
    false  # Prevents default violations
}

# Risk level calculation that policies should override
risk_level = "low" {
    true  # Default risk level
}

# Required trace level that policies should override
trace_level = "basic" {
    true  # Default trace level
}

# Standard metadata structure that policies should extend
metadata = {} {
    true  # Default empty metadata
}

# Standardized result format that all policies must use
result = {
    "allow": allow,
    "violations": violation_messages,
    "risk_level": risk_level,
    "trace_level": trace_level,
    "metadata": metadata
} {
    # Collect all violations into an array
    violation_messages := [msg | msg = violations[msg]]
}

# Helper to validate input structure
valid_input {
    input.response
    input.trace_context
}

# Common input validation rule
violations[msg] {
    not valid_input
    msg := "Invalid input structure: missing required fields"
}