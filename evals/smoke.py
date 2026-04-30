from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.scorer import includes
from inspect_ai.solver import generate


@task
def smoke() -> Task:
    return Task(
        dataset=[
            Sample(input="What is 2+2? Reply with just the number.", target="4"),
            Sample(input="Capital of France? One word.", target="Paris"),
            Sample(input="Reverse the word 'cat'.", target="tac"),
            Sample(input="Is the sky blue? Yes or no.", target="Yes"),
            Sample(input="Name a prime between 10 and 20.", target=["11", "13", "17", "19"]),
        ],
        solver=generate(),
        scorer=includes(),
    )
