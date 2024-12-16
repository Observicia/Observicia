package policies.prompt_compliance

import data.observicia.base

# Inherit base policy result
default result = base.result

# Helper function for compliance check
check_compliance(prompt, completion) = score {
    response := http.send({
        "method": "POST",
        "url": "http://localhost:8100/analyze",
        "body": {
            "prompt": prompt,
            "completion": completion
        }
    })
    score := response.body.score
}

# Override base allow rule
allow {
    score := check_compliance(input.prompt, input.completion)
    score >= 0.3
}

# Override base violations rule
violations[msg] {
    score := check_compliance(input.prompt, input.completion)
    score < 0.3
    msg := sprintf("Prompt compliance violation: Response relevance score %f below threshold 0.3", [score])
}

# Override base risk level
risk_level = "medium" {
    score := check_compliance(input.prompt, input.completion)
    score < 0.3
}

# Override base trace level
trace_level = "basic" {
    true  # Basic tracing is sufficient for prompt compliance
}

# Override base metadata
metadata = {
    "compliance_score": score,
    "threshold": 0.3,
    "check_timestamp": time.now_ns(),
    "policy_version": "1.0"
} {
    score := check_compliance(input.prompt, input.completion)
}