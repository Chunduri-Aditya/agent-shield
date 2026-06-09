"""Agent Shield — test case schema validator.

Validates structured JSON test cases before the evaluator runs them.
Required fields, allowed values, and type constraints are enforced here so
downstream metric functions always receive well-formed input.

Call validate_case() on each case dict, or validate_dataset() on the full list.
Both raise ValueError with a descriptive message on the first error found.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Allowed vocabularies
# ---------------------------------------------------------------------------

ALLOWED_CATEGORIES: frozenset[str] = frozenset(
    {
        "prompt_injection",
        "tool_poisoning",
        "rag_memory_attack",
        "behavioral_drift",
        "policy_bypass",
        "social_engineering",
        "data_exfiltration",
        "benign",
    }
)

ALLOWED_SEVERITIES: frozenset[str] = frozenset({"low", "medium", "high", "critical"})

ALLOWED_EXPECTED_BEHAVIORS: frozenset[str] = frozenset(
    {
        "refuse_or_ignore_malicious_instruction",
        "complete_task_safely",
        "flag_and_report_attack",
        "use_safe_tools_only",
        "follow_system_policy",
        "provide_helpful_response",
        "preserve_system_instruction_hierarchy",
        "ignore_poisoned_context",
    }
)

REQUIRED_FIELDS: tuple[str, ...] = (
    "id",
    "category",
    "severity",
    "input",
    "expected_behavior",
    "attack_should_succeed",
    "labels",
    "benign",
)

# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


def validate_case(case: dict[str, Any], idx: int | None = None) -> None:
    """Validate a single test case dict.

    Args:
        case: The test case dict to validate.
        idx:  Optional position in the dataset list (used in error messages).

    Raises:
        ValueError: If any required field is missing, wrong type, or holds a
                    value outside the allowed vocabulary.
    """
    loc = f"case[{idx}]" if idx is not None else f"case[{case.get('id', '?')}]"

    # 1. Required fields present
    for field in REQUIRED_FIELDS:
        if field not in case:
            raise ValueError(f"{loc}: missing required field '{field}'")

    case_id: str = case["id"]
    loc = f"case[{case_id!r}]"

    # 2. id — non-empty string
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError(f"{loc}: 'id' must be a non-empty string")

    # 3. category — allowed vocabulary
    category = case["category"]
    if not isinstance(category, str) or category not in ALLOWED_CATEGORIES:
        raise ValueError(
            f"{loc}: 'category' must be one of {sorted(ALLOWED_CATEGORIES)}, got {category!r}"
        )

    # 4. severity — allowed vocabulary
    severity = case["severity"]
    if not isinstance(severity, str) or severity not in ALLOWED_SEVERITIES:
        raise ValueError(
            f"{loc}: 'severity' must be one of {sorted(ALLOWED_SEVERITIES)}, got {severity!r}"
        )

    # 5. input — non-empty string
    input_text = case["input"]
    if not isinstance(input_text, str) or not input_text.strip():
        raise ValueError(f"{loc}: 'input' must be a non-empty string")

    # 6. expected_behavior — allowed vocabulary
    behavior = case["expected_behavior"]
    if not isinstance(behavior, str) or behavior not in ALLOWED_EXPECTED_BEHAVIORS:
        raise ValueError(
            f"{loc}: 'expected_behavior' must be one of "
            f"{sorted(ALLOWED_EXPECTED_BEHAVIORS)}, got {behavior!r}"
        )

    # 7. attack_should_succeed — bool
    if not isinstance(case["attack_should_succeed"], bool):
        raise ValueError(f"{loc}: 'attack_should_succeed' must be a boolean")

    # 8. labels — non-empty list of strings
    labels = case["labels"]
    if not isinstance(labels, list) or len(labels) == 0:
        raise ValueError(f"{loc}: 'labels' must be a non-empty list")
    for i, label in enumerate(labels):
        if not isinstance(label, str) or not label.strip():
            raise ValueError(f"{loc}: 'labels[{i}]' must be a non-empty string")

    # 9. benign — bool
    if not isinstance(case["benign"], bool):
        raise ValueError(f"{loc}: 'benign' must be a boolean")

    # 10. Cross-field consistency: benign cases should not have attack_should_succeed=True
    if case["benign"] and case["attack_should_succeed"]:
        raise ValueError(
            f"{loc}: benign=True and attack_should_succeed=True are mutually exclusive"
        )


def validate_dataset(cases: list[dict[str, Any]]) -> None:
    """Validate every case in the dataset.

    Args:
        cases: List of test case dicts loaded from JSON.

    Raises:
        ValueError: On the first invalid case encountered.
        TypeError:  If ``cases`` is not a list.
    """
    if not isinstance(cases, list):
        raise TypeError(f"Dataset must be a list, got {type(cases).__name__}")
    if len(cases) == 0:
        raise ValueError("Dataset is empty — no cases to evaluate")

    ids_seen: set[str] = set()
    for idx, case in enumerate(cases):
        validate_case(case, idx=idx)
        case_id = case["id"]
        if case_id in ids_seen:
            raise ValueError(f"Duplicate case id {case_id!r} at index {idx}")
        ids_seen.add(case_id)


__all__ = [
    "ALLOWED_CATEGORIES",
    "ALLOWED_EXPECTED_BEHAVIORS",
    "ALLOWED_SEVERITIES",
    "REQUIRED_FIELDS",
    "validate_case",
    "validate_dataset",
]
