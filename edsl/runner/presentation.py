"""Answer-associated snapshots of the question actually presented for execution."""

from copy import deepcopy
from typing import Any


def capture_presentation(
    question: dict[str, Any] | None,
    *,
    source: str,
    read_versions: tuple[tuple[str, int], ...] = (),
) -> dict[str, Any] | None:
    """Detach displayed attributes and read references; never copy the state view.

    Capture before calling an agent/model, not by rendering the template again
    when assembling Results. Missing runtime definitions retain legacy behavior.
    """
    if question is None:
        return None
    return {
        "version": 1,
        "source": source,
        "attributes": deepcopy(
            {
                key: question[key]
                for key in (
                    "question_text",
                    "question_type",
                    "question_options",
                    "question_items",
                    "option_labels",
                )
                if key in question
            }
        ),
        "shared_state_reads": [
            {"read_id": read_id, "version": version}
            for read_id, version in read_versions
        ],
    }
