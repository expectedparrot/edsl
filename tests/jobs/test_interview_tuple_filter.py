"""Index filters retain the template sandbox's attribute and call restrictions."""

from types import SimpleNamespace

import pytest
from jinja2 import UndefinedError
from jinja2.exceptions import SecurityError

from edsl.jobs.interview_tuple_filter import InterviewTupleFilter
from edsl.utilities.jinja import make_environment


@pytest.fixture
def components():
    return [[SimpleNamespace(_index=i) for i in range(3)] for _ in range(3)]


def test_filter_matches_indices_across_all_three_components(components):
    selected = InterviewTupleFilter(
        *components,
        "{{ agent._index == scenario._index and scenario._index == model._index }}",
    )
    assert [(a._index, s._index, m._index) for a, s, m in selected] == [
        (0, 0, 0),
        (1, 1, 1),
        (2, 2, 2),
    ]


@pytest.mark.parametrize(
    "expression",
    [
        "{{ agent.__class__ == scenario.__class__ }}",
        "{{ agent._position_index == scenario._position_index }}",
        "{{ agent.nested._index == scenario._index }}",
        "{{ agent.mutate() }}",
    ],
)
def test_filter_rejects_other_private_attributes_and_calls(components, expression):
    touched = []
    for group in components:
        for item in group:
            item._position_index = item._index
            item.nested = SimpleNamespace(_index=item._index)
            item.mutate = lambda: touched.append(True)
    with pytest.raises(SecurityError):
        list(InterviewTupleFilter(*components, expression))
    assert touched == []


def test_filter_rejects_missing_attributes_instead_of_matching_undefineds(components):
    with pytest.raises(UndefinedError):
        list(
            InterviewTupleFilter(*components, "{{ agent.missing == scenario.missing }}")
        )


@pytest.mark.parametrize("value", ["0", True, lambda: 0])
def test_filter_only_exposes_integer_indices(components, value):
    components[0][0]._index = value
    with pytest.raises(SecurityError):
        list(InterviewTupleFilter(*components, "{{ agent._index == scenario._index }}"))


def test_index_exception_does_not_change_other_template_environments(components):
    template = make_environment().from_string("{{ agent._index is defined }}")
    assert template.render(agent=components[0][0]) == "False"
