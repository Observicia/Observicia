package policies.prompt_compliance

default allow = false

allow {
    prompt_compliant
}

# Check prompt compliance
prompt_compliant {
    score := prompt_compliance_check(input.prompt, input.completion)
    score >= 0.3  # TODO Make this as a configurable threshold
}

violation[msg] {
    score := prompt_compliance_check(input.prompt, input.completion)
    score < 0.3
    msg := sprintf("Prompt compliance score too low: %f", [score])
}

prompt_compliance_check(prompt, completion) = score {
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
