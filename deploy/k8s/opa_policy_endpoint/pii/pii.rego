package policies.pii

import data.observicia.base

# Inherit base policy result
default result = base.result

# Helper functions
check_pii_entities(text) = entities {
    response := http.send({
        "method": "POST",
        "url": "http://localhost:8000/analyze",
        "headers": {"Content-Type": "application/json"},
        "body": {"text": text}
    })
    response.status_code == 200
    entities := response.body
}

extract_text(response) = text {
    text := response.choices[0].message.content
}

# Override base allow rule
allow {
    text := extract_text(input.response)
    entities := check_pii_entities(text)
    count(entities) == 0
}

# Override base violations rule
violations[msg] {
    text := extract_text(input.response)
    entity := check_pii_entities(text)[_]
    msg := sprintf("PII violation: Found %s entity with confidence %f", [entity.entity_type, entity.score])
}

# Override base risk level
risk_level = "high" {
    text := extract_text(input.response)
    count(check_pii_entities(text)) > 0
}

# Override base trace level
trace_level = "enhanced" {
    true  # PII checks always require enhanced tracing
}

# Override base metadata
metadata = {
    "pii_detected": count_pii > 0,
    "pii_entities": entities,
    "scan_timestamp": time.now_ns(),
    "policy_version": "1.0"
} {
    text := extract_text(input.response)
    entities := check_pii_entities(text)
    count_pii := count(entities)
}