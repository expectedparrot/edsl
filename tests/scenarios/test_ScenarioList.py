import pytest
from edsl.scenarios import Scenario, ScenarioList
import tempfile
import os


def test_expand():
    s = ScenarioList([Scenario({"a": 1, "b": [1, 2]})])
    expanded = s.expand("b")
    expected = ScenarioList([Scenario({"a": 1, "b": 1}), Scenario({"a": 1, "b": 2})])
    assert expanded == expected


def test_exports():
    # just test coverts do not throw exceptions
    s = ScenarioList.example()
    _ = s.to_pandas()
    _ = s.to_csv()
    _ = s.to_dicts()
    _ = s.to_list()
    
def test_filter():
    s = ScenarioList([Scenario({"a": 1, "b": 1}), Scenario({"a": 1, "b": 2})])
    filtered = s.filter("b == 2")
    expected = ScenarioList([Scenario({"a": 1, "b": 2})])
    assert filtered == expected


def test_from_csv():
    with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".csv") as f:
        _ = f.write("name,age,location\nAlice,30,New York\nBob,25,Los Angeles\n")
        temp_filename = f.name

    scenario_list = ScenarioList.from_source("csv", temp_filename)
    os.remove(temp_filename)  # Clean up the temp file

    assert len(scenario_list) == 2
    assert scenario_list[0]["name"] == "Alice"
    assert scenario_list[1]["age"] == "25"


def test_to_dict():
    s = ScenarioList(
        [Scenario({"food": "wood chips"}), Scenario({"food": "wood-fired pizza"})]
    )
    result = s.to_dict()
    assert isinstance(result, dict)
    assert "scenarios" in result
    assert len(result["scenarios"]) == 2
    assert result["scenarios"][0]["food"] == "wood chips"
    assert result["scenarios"][1]["food"] == "wood-fired pizza"


def test_uniquify_basic():
    """Test basic uniquify with duplicate values."""
    sl = ScenarioList([
        Scenario({"id": "item", "value": 1}),
        Scenario({"id": "item", "value": 2}),
        Scenario({"id": "item", "value": 3}),
        Scenario({"id": "other", "value": 4})
    ])
    unique_sl = sl.uniquify("id")
    ids = [s["id"] for s in unique_sl]
    assert ids == ['item', 'item_1', 'item_2', 'other']


def test_uniquify_no_duplicates():
    """Test uniquify when there are no duplicates."""
    sl = ScenarioList([
        Scenario({"id": "a", "value": 1}),
        Scenario({"id": "b", "value": 2}),
        Scenario({"id": "c", "value": 3})
    ])
    unique_sl = sl.uniquify("id")
    ids = [s["id"] for s in unique_sl]
    assert ids == ['a', 'b', 'c']


def test_uniquify_chaining():
    """Test that uniquify can be chained with other methods."""
    sl = ScenarioList([
        Scenario({"id": "test", "x": 1}),
        Scenario({"id": "test", "x": 2})
    ])
    result = sl.uniquify("id").add_value("status", "active")
    ids = [s["id"] for s in result]
    statuses = [s["status"] for s in result]
    assert ids == ['test', 'test_1']
    assert all(s == "active" for s in statuses)


def test_uniquify_numeric_values():
    """Test uniquify with numeric field values."""
    sl = ScenarioList([
        Scenario({"id": 100, "value": "a"}),
        Scenario({"id": 100, "value": "b"}),
        Scenario({"id": 200, "value": "c"})
    ])
    unique_sl = sl.uniquify("id")
    ids = [s["id"] for s in unique_sl]
    assert ids == [100, '100_1', 200]


def test_uniquify_nonexistent_field():
    """Test that uniquify raises error when field doesn't exist."""
    sl = ScenarioList([Scenario({"a": 1}), Scenario({"a": 2})])
    with pytest.raises(Exception):  # Should raise ScenarioError
        sl.uniquify("nonexistent")


if __name__ == "__main__":
    pytest.main()
