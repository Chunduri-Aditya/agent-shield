from evals.inputs import BASELINE_USER_TASK, make_samples
from evals.smoke import smoke
from inputs import ATTACKS
from tools.attacks import TOOL_ATTACK_BY_ID


def test_inputs_registry_has_five_attacks() -> None:
    assert len(ATTACKS) == 5


def test_inputs_eval_builds_one_sample_per_attack() -> None:
    samples = make_samples(BASELINE_USER_TASK)
    assert len(samples) == len(ATTACKS)


def test_tools_registry_marks_tl01_implemented() -> None:
    assert TOOL_ATTACK_BY_ID["TL-01"].implemented is True


def test_smoke_eval_contains_five_samples() -> None:
    task = smoke()
    assert len(task.dataset) == 5
