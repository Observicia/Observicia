from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
import requests
from opentelemetry import trace


@dataclass
class Policy:
    """Represents an OPA policy configuration."""
    name: str
    path: str  # Path part of the URL after /v1/data/
    description: Optional[str] = None
    required_trace_level: str = "basic"
    risk_level: str = "low"


@dataclass
class PolicyResult:
    """Result of a policy evaluation."""
    passed: bool
    violations: List[str]
    required_trace_level: str = "basic"  # "basic" or "enhanced"
    metadata: Dict[str, Any] = field(default_factory=dict)
    risk_level: str = "low"  # "low", "medium", "high", "critical"


@dataclass
class Policy:
    """Represents an OPA policy configuration."""
    name: str
    path: str  # Path part of the URL after /v1/data/
    description: Optional[str] = None
    required_trace_level: str = "basic"
    risk_level: str = "low"


class PolicyEngine:
    """
    Policy engine that integrates with OPA for policy evaluation.
    """

    def __init__(self,
                 opa_endpoint: str,
                 policies: Optional[List[Policy]] = None) -> None:
        """
        Initialize PolicyEngine with OPA endpoint and policies.
        
        Args:
            opa_endpoint: Base URL of the OPA server
            policies: List of Policy objects defining available policies
        """
        self.opa_endpoint = opa_endpoint.rstrip('/')

        self.policies: Dict[str, Policy] = {
            p.name: p
            for p in (policies or [])
        }
        self.active_policies: Set[str] = set(self.policies.keys())
        self.tracer = trace.get_tracer(__name__)

    async def evaluate_with_context(
            self,
            eval_context: Dict[str, Any],
            prompt: Optional[str] = None,
            completion: Optional[str] = None,
            policies: Optional[List[str]] = None) -> PolicyResult:
        """
        Evaluate specified policies with given context.
        
        Args:
            eval_context: Context data to evaluate against policies
            prompt: Optional prompt text for prompt compliance check
            completion: Optional completion text for prompt compliance check
            policies: List of policy names to evaluate. If None, use active policies.
        """
        with self.tracer.start_span("policy_evaluation") as span:
            # Use specified policies or fall back to active policies
            policy_names = policies if policies is not None else list(
                self.active_policies)

            # Filter to only existing policies
            policies_to_evaluate = [
                self.policies[name] for name in policy_names
                if name in self.policies
            ]

            # Add prompt and completion to evaluation context if provided
            if prompt is not None and completion is not None:
                eval_context["prompt"] = prompt
                eval_context["completion"] = completion

            result = await self._evaluate_policies(eval_context,
                                                   policies_to_evaluate)

            span.set_attributes({
                "policy_count":
                len(policies_to_evaluate),
                "violations":
                len(result.violations),
                "risk_level":
                result.risk_level,
                "evaluated_policies":
                ";".join(p.name for p in policies_to_evaluate)
            })

            return result

    def evaluate_sync(self,
                      eval_context: Dict[str, Any],
                      prompt: Optional[str] = None,
                      completion: Optional[str] = None) -> PolicyResult:
        """
        Synchronously evaluate policies with given context.
        """
        with self.tracer.start_span("policy_evaluation") as span:
            policies_to_evaluate = [
                self.policies[name] for name in self.active_policies
                if name in self.policies
            ]

            # Add prompt and completion to evaluation context if provided
            if prompt is not None and completion is not None:
                eval_context["prompt"] = prompt
                eval_context["completion"] = completion

            result = self._evaluate_policies_sync(eval_context,
                                                  policies_to_evaluate)

            span.set_attributes({
                "policy_count":
                len(policies_to_evaluate),
                "violations":
                len(result.violations),
                "risk_level":
                result.risk_level,
                "evaluated_policies":
                ";".join(p.name for p in policies_to_evaluate)
            })

            return result

    def _evaluate_policies_sync(self, eval_context: Dict[str, Any],
                                policies: List[Policy]) -> PolicyResult:
        """Evaluate multiple policies synchronously and aggregate results."""
        violations = []
        metadata = {}
        max_trace_level = "basic"
        max_risk_level = "low"

        for policy in policies:
            raw_result = self._evaluate_single_policy_sync(
                policy, eval_context)
            # print(f'Policy: {policy.name}, Result: {raw_result}')

            # Extract the nested result
            result = raw_result.get('result', {})

            if not result.get("allow", False):
                # Get violations from the nested result
                policy_violations = result.get("violations", [])
                if policy_violations:
                    violations.extend(f"{policy.name}: {v}"
                                      for v in policy_violations)
                else:
                    # If no specific violations but policy failed, add metadata as context
                    policy_metadata = result.get("metadata", {})
                    violation_context = []
                    if policy_metadata.get("pii_detected"):
                        pii_entities = policy_metadata.get("pii_entities", [])
                        for entity in pii_entities:
                            violation_context.append(
                                f"Found {entity['entity_type']} with confidence {entity['score']}"
                            )
                    if violation_context:
                        violations.extend(f"{policy.name}: {v}"
                                          for v in violation_context)
                    else:
                        violations.append(
                            f"{policy.name}: Policy check failed")

            # Get trace level from nested result or policy default
            policy_trace_level = result.get("trace_level",
                                            policy.required_trace_level)
            if policy_trace_level == "enhanced":
                max_trace_level = "enhanced"

            # Get risk level from nested result or policy default
            risk_level = result.get("risk_level", policy.risk_level)
            if self._compare_risk_levels(risk_level, max_risk_level) > 0:
                max_risk_level = risk_level

            # Store metadata from nested result
            metadata[policy.name] = result.get("metadata", {})

        return PolicyResult(passed=len(violations) == 0,
                            violations=violations,
                            required_trace_level=max_trace_level,
                            metadata=metadata,
                            risk_level=max_risk_level)

    def _evaluate_single_policy_sync(
            self, policy: Policy, eval_context: Dict[str,
                                                     Any]) -> Dict[str, Any]:
        """Evaluate a single policy synchronously using OPA."""
        url = f"{self.opa_endpoint}/v1/data/{policy.path}"
        try:
            response = requests.post(url, json={"input": eval_context})
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "allow":
                    False,
                    "violations":
                    [f"Policy evaluation failed: HTTP {response.status_code}"],
                    "risk_level":
                    "high"
                }
        except Exception as e:
            return {
                "allow": False,
                "violations": [f"Policy evaluation error: {str(e)}"],
                "risk_level": "high"
            }

    def _compare_risk_levels(self, level1: str, level2: str) -> int:
        """Compare two risk levels. Returns positive if level1 > level2."""
        risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        return risk_order.get(level1, 0) - risk_order.get(level2, 0)

    def add_policy(self, policy: Policy) -> None:
        """Add a policy to the available policies."""
        self.policies[policy.name] = policy
        self.active_policies.add(policy.name)

    def remove_policy(self, policy_name: str) -> None:
        """Remove a policy from the available and active policies."""
        if policy_name in self.policies:
            del self.policies[policy_name]
            self.active_policies.discard(policy_name)

    def activate_policy(self, policy_name: str) -> None:
        """Activate a policy if it exists."""
        if policy_name in self.policies:
            self.active_policies.add(policy_name)

    def deactivate_policy(self, policy_name: str) -> None:
        """Deactivate a policy without removing it."""
        self.active_policies.discard(policy_name)

    @property
    def available_policies(self) -> List[Policy]:
        """Get list of all available policies."""
        return list(self.policies.values())
