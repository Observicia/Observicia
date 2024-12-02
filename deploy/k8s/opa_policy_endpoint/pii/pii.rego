package policies.pii

import future.keywords.if
import future.keywords.in

default allow := false

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

# Main rules
allow {
    text := extract_text(input.response)
    entities := check_pii_entities(text)
    count(entities) == 0
}

violations[msg] {
    text := extract_text(input.response)
    entity := check_pii_entities(text)[_]
    msg := sprintf("Found PII of type %s: '%s'", [entity.type, entity.text])
}

risk_level = "high" {
    text := extract_text(input.response)
    count(check_pii_entities(text)) > 0
}

risk_level = "low" {
    text := extract_text(input.response)
    count(check_pii_entities(text)) == 0
}

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