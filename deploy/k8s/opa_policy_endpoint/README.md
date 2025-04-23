# Observicia OPA Policy

Policy implementation for Observicia Open Policy Agent (OPA) endpoint.

## Structure

```
opa_policy_endpoint/
├── base/
│   └── base.rego         # Base template
└── policies/            # Policy implementations
    ├── pii/
    │   └── policy.rego
    └── prompt-compliance/
        └── policy.rego
```

## Standard Result Structure

All policies must return:
```json
{
    "allow": boolean,           # Decision
    "violations": string[],     # Violation messages
    "risk_level": string,       # low|medium|high|critical
    "trace_level": string,      # basic|enhanced
    "metadata": object          # Policy-specific data
}
```

## Creating a New Policy

1. Create new policy file:
```bash
mkdir -p policies/my-policy
touch policies/my-policy/policy.rego
```

2. Basic template:
```rego
package policies.my_policy
import data.observicia.base

# Inherit base
default result = base.result

# Core rules to implement
allow {
    # Your allow conditions
}

violations[msg] {
    # Your violation conditions
    msg := "Violation message"
}

risk_level = "medium" {
    # Risk conditions
}

# Optional overrides
trace_level = "basic" {
    true
}

metadata = {
    "policy_version": "1.0"
} {
    true
}
```

## Testing

Quick test using OPA REPL:
```bash
$ opa run base/base.rego policies/my-policy/policy.rego
> input := {"response": {"choices": [{"message": {"content": "test"}}]}}
> data.policies.my_policy.result
```

## Example Policy

Length check example:
```rego
package policies.text_length
import data.observicia.base

default result = base.result

allow {
    count(input.response.choices[0].message.content) <= 1000
}

violations[msg] {
    length := count(input.response.choices[0].message.content)
    length > 1000
    msg := sprintf("Text length %d exceeds limit", [length])
}

risk_level = "medium" {
    count(input.response.choices[0].message.content) > 1000
}
```

## Notes

1. **Always extend base**
   - Import `observicia.base`
   - Set default result
   - Implement required rules

2. **Required rules**
   - `allow`: Decision logic
   - `violations`: Error messages
   - `risk_level`: Impact severity

3. **Input structure**
```json
{
    "response": {
        "choices": [{
            "message": {
                "content": "string"
            }
        }]
    },
    "prompt": "string",      # Optional
    "completion": "string",  # Optional
    "trace_context": {}      # Added by SDK
}
```

4. **Risk levels**
   - low: Minor issues
   - medium: Notable concerns
   - high: Serious issues
   - critical: Must block

## Deployment

Add to OPA ConfigMap:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: opa-policies
data:
  "base/base.rego": |
    # Base template
  "policies/my-policy/policy.rego": |
    # Policy content
```

Configure in SDK:
```yaml
policies:
  - name: my-policy
    path: policies/my_policy
    description: "Description"
    required_trace_level: basic
    risk_level: medium
```