import pytest

from edsl.sharedstate import decode_matrix
from edsl.sharedstate.dsl_runtime import DSLValidationError, Runtime


ROWS = ["Hike", "Sailing"]
OPTIONS = ["up", "neutral", "down"]


def evaluate(answer):
    return Runtime().evaluate(
        decode_matrix(answer, rows=ROWS, options=OPTIONS),
        {"state": {}, "input": {}, "constant": {}, "current": {}},
    )


def test_decode_matrix_positional_codes():
    assert evaluate({"0": 0, "1": 2}) == {"Hike": "up", "Sailing": "down"}


def test_decode_matrix_accepts_domain_values():
    assert evaluate({"Hike": "neutral", "Sailing": "up"}) == {
        "Hike": "neutral",
        "Sailing": "up",
    }


@pytest.mark.parametrize(
    "answer, message",
    [
        ({"0": 0}, "missing rows"),
        ({"0": 0, "Hike": 1, "1": 2}, "duplicate matrix row"),
        ({"0": 0, "2": 1}, "unknown matrix row"),
        ({"0": 0, "1": 4}, "unknown matrix option"),
        ([0, 1], "matrix answer must be a map"),
    ],
)
def test_decode_matrix_rejects_malformed_answers(answer, message):
    with pytest.raises(DSLValidationError, match=message):
        evaluate(answer)
