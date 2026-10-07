"""Generated round-trip checks over sparse rows and nested JSON values."""

import tempfile

import pytest

pytest.importorskip("datasets")
pytest.importorskip("hypothesis")
from hypothesis import given, settings, strategies as st

from edsl import Agent, AgentList, Scenario, ScenarioList

scalar = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(-(2**63), 2**63 - 1),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(),
)
json_value = st.recursive(
    scalar,
    lambda child: st.one_of(
        st.lists(child, max_size=4), st.dictionaries(st.text(), child, max_size=4)
    ),
    max_leaves=12,
)
row = st.fixed_dictionaries(
    {},
    optional={
        "integer": st.one_of(st.none(), st.integers(-(2**63), 2**63 - 1)),
        "number": st.one_of(
            st.integers(-(2**63), 2**63 - 1),
            st.floats(allow_nan=False, allow_infinity=False),
        ),
        "text": st.one_of(st.none(), st.text()),
        "nested": st.dictionaries(st.text(), json_value, max_size=3),
        "items": st.lists(json_value, max_size=4),
    },
)


@settings(max_examples=40, deadline=None, database=None)
@given(st.lists(row, max_size=8))
def test_generated_default_roundtrip(rows):
    for cls, item in [(AgentList, Agent), (ScenarioList, Scenario)]:
        original = cls([item(r) for r in rows])
        with tempfile.TemporaryDirectory() as tmp:
            original.save_hf(tmp)
            restored = cls.load_hf(tmp)
            assert restored == original
            assert [
                dict(x.traits) if cls is AgentList else dict(x) for x in restored
            ] == rows


@settings(max_examples=30, deadline=None, database=None)
@given(st.lists(json_value, max_size=8))
def test_generated_coercion_roundtrip(values):
    original = ScenarioList([Scenario({"value": value}) for value in values])
    for coerce in ("string", "json"):
        with tempfile.TemporaryDirectory() as tmp:
            original.save_hf(tmp, coerce=coerce)
            restored = ScenarioList.load_hf(tmp)
            assert restored == original
            assert [dict(r) for r in restored] == [{"value": v} for v in values]
