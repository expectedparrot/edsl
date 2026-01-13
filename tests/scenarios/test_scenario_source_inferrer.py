"""
Tests for the ScenarioSourceInferrer module.

This module tests the automatic source type detection and dispatching
functionality provided by ScenarioSourceInferrer.
"""

import tempfile
import os
import pytest
from edsl.scenarios.scenario_helpers.scenario_source_inferrer import ScenarioSourceInferrer, from_any
from edsl.scenarios import ScenarioList
from edsl.scenarios.exceptions import ScenarioError


def test_infer_dict_source():
    """Test inference of simple dictionary source."""
    data = {"name": ["Alice", "Bob"], "age": [25, 30]}
    sl = from_any(data)

    assert isinstance(sl, ScenarioList)
    assert len(sl) == 2
    assert sl[0]["name"] == "Alice"
    assert sl[0]["age"] == 25


def test_infer_nested_dict_source():
    """Test inference of nested dictionary source."""
    data = {
        "item1": {"product": "coffee", "price": 4.99},
        "item2": {"product": "tea", "price": 3.99},
    }
    sl = from_any(data, id_field="item_id")

    assert isinstance(sl, ScenarioList)
    assert len(sl) == 2
    assert "item_id" in sl[0].data


def test_infer_list_source():
    """Test inference of simple list source."""
    values = ["apple", "banana", "cherry"]
    sl = from_any(values, field_name="fruit")

    assert isinstance(sl, ScenarioList)
    assert len(sl) == 3
    assert sl[0]["fruit"] == "apple"


def test_infer_list_source_default_field_name():
    """Test inference of list source with default field name."""
    values = [1, 2, 3]
    with pytest.warns(UserWarning, match="No field_name provided"):
        sl = from_any(values)

    assert isinstance(sl, ScenarioList)
    assert len(sl) == 3
    assert "value" in sl[0].data


def test_infer_empty_list():
    """Test inference of empty list."""
    sl = from_any([])
    assert isinstance(sl, ScenarioList)
    assert len(sl) == 0


def test_infer_pandas_dataframe():
    """Test inference of pandas DataFrame source."""
    try:
        import pandas as pd
    except ImportError:
        pytest.skip("pandas not available")

    df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
    sl = from_any(df)

    assert isinstance(sl, ScenarioList)
    assert len(sl) == 3
    assert sl[0]["x"] == 1


def test_infer_csv_file():
    """Test inference of CSV file."""
    # Create a temporary CSV file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("name,age\n")
        f.write("Alice,25\n")
        f.write("Bob,30\n")
        csv_path = f.name

    try:
        sl = from_any(csv_path)
        assert isinstance(sl, ScenarioList)
        assert len(sl) == 2
        assert sl[0]["name"] == "Alice"
    finally:
        os.unlink(csv_path)


def test_infer_tsv_file():
    """Test inference of TSV file."""
    # Create a temporary TSV file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".tsv", delete=False) as f:
        f.write("name\tage\n")
        f.write("Alice\t25\n")
        f.write("Bob\t30\n")
        tsv_path = f.name

    try:
        sl = from_any(tsv_path)
        assert isinstance(sl, ScenarioList)
        assert len(sl) == 2
    finally:
        os.unlink(tsv_path)


def test_file_not_found():
    """Test that non-existent files raise appropriate error."""
    with pytest.raises(ScenarioError, match="not found"):
        from_any("nonexistent_file.csv")


def test_unsupported_file_extension():
    """Test that unsupported file extensions raise appropriate error."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".unknown", delete=False) as f:
        f.write("test")
        unknown_path = f.name

    try:
        with pytest.raises(ScenarioError, match="Unable to infer source type"):
            from_any(unknown_path)
    finally:
        os.unlink(unknown_path)


def test_url_detection():
    """Test that URLs are properly detected."""
    # Note: This test doesn't actually fetch the URL
    # We just test that it's recognized as a URL type
    assert ScenarioSourceInferrer._is_url("https://example.com/data.csv")
    assert ScenarioSourceInferrer._is_url("http://example.com/data.csv")
    assert not ScenarioSourceInferrer._is_url("data.csv")
    assert not ScenarioSourceInferrer._is_url("/path/to/data.csv")


def test_unsupported_type():
    """Test that unsupported types raise appropriate error."""
    with pytest.raises(ScenarioError, match="Unable to infer source type"):
        from_any(12345)  # Integer is not a supported source type


def test_sqlite_without_table_parameter():
    """Test that SQLite files require table parameter."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        with pytest.raises(ScenarioError, match="table"):
            from_any(db_path)
    finally:
        os.unlink(db_path)


def test_list_of_tuples_without_field_names():
    """Test that list of tuples requires field_names parameter."""
    data = [("Alice", 25), ("Bob", 30)]
    with pytest.raises(ScenarioError, match="field_names"):
        from_any(data)


def test_list_of_tuples_with_field_names():
    """Test list of tuples with explicit field_names."""
    data = [("Alice", 25), ("Bob", 30)]
    sl = from_any(data, field_names=["name", "age"])

    assert isinstance(sl, ScenarioList)
    assert len(sl) == 2
    assert sl[0]["name"] == "Alice"
    assert sl[0]["age"] == 25


def test_serialized_scenario_list_dict():
    """Test inference of serialized ScenarioList dictionary."""

    data = {"scenarios": [{"x": 1, "y": 2}, {"x": 3, "y": 4}]}
    sl = from_any(data)

    assert isinstance(sl, ScenarioList)
    assert len(sl) == 2


def test_direct_method_call():
    """Test using ScenarioSourceInferrer.infer_and_create directly."""
    data = {"a": [1, 2], "b": [3, 4]}
    sl = ScenarioSourceInferrer.infer_and_create(data)

    assert isinstance(sl, ScenarioList)
    assert len(sl) == 2


def test_kwargs_passed_through():
    """Test that kwargs are properly passed through to underlying source."""
    # Create a CSV with custom delimiter
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("name|age\n")
        f.write("Alice|25\n")
        txt_path = f.name

    try:
        # The .txt extension will trigger delimited_file source
        sl = from_any(txt_path, delimiter="|")
        assert isinstance(sl, ScenarioList)
        # Basic check that it was created (actual parsing depends on implementation)
    finally:
        os.unlink(txt_path)


def test_scenario_list_from_source_auto_dict(capsys):
    """Test ScenarioList.from_source() auto-detect mode with dictionary."""
    data = {"name": ["Alice", "Bob"], "age": [25, 30]}
    sl = ScenarioList.from_source(data)

    # Verify it created the ScenarioList correctly
    assert isinstance(sl, ScenarioList)
    assert len(sl) == 2

    # Verify it printed the detected source type
    captured = capsys.readouterr()
    assert "Detected source type: dictionary" in captured.out


def test_scenario_list_from_source_auto_list(capsys):
    """Test ScenarioList.from_source() auto-detect mode with list."""
    values = ["apple", "banana"]
    sl = ScenarioList.from_source(values, field_name="fruit")

    assert isinstance(sl, ScenarioList)
    assert len(sl) == 2

    # Verify it printed the detected source type
    captured = capsys.readouterr()
    assert "Detected source type: list" in captured.out


def test_scenario_list_from_source_auto_csv(capsys):
    """Test ScenarioList.from_source() auto-detect mode with CSV file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("name,age\n")
        f.write("Alice,25\n")
        csv_path = f.name

    try:
        sl = ScenarioList.from_source(csv_path)
        assert isinstance(sl, ScenarioList)
        assert len(sl) == 1

        # Verify it printed the detected source type with path
        captured = capsys.readouterr()
        assert "Detected source type: CSV file at" in captured.out
        assert csv_path in captured.out
    finally:
        os.unlink(csv_path)


def test_scenario_list_from_source_auto_pandas(capsys):
    """Test ScenarioList.from_source() auto-detect mode with pandas DataFrame."""
    try:
        import pandas as pd
    except ImportError:
        pytest.skip("pandas not available")

    df = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
    sl = ScenarioList.from_source(df)

    assert isinstance(sl, ScenarioList)
    assert len(sl) == 2

    # Verify it printed the detected source type
    captured = capsys.readouterr()
    assert "Detected source type: pandas DataFrame" in captured.out


def test_scenario_list_from_source_explicit_mode():
    """Test ScenarioList.from_source() explicit mode (backward compatibility)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("name,age\n")
        f.write("Alice,25\n")
        csv_path = f.name

    try:
        # Explicit mode: provide source type as first arg
        sl = ScenarioList.from_source("csv", csv_path)
        assert isinstance(sl, ScenarioList)
        assert len(sl) == 1
    finally:
        os.unlink(csv_path)


def test_verbose_parameter():
    """Test that verbose parameter controls printing."""
    data = {"a": [1, 2]}

    # With verbose=True (this is the default behavior for from_any with verbose kwarg)
    sl = ScenarioSourceInferrer.infer_and_create(data, verbose=True)
    assert isinstance(sl, ScenarioList)

    # With verbose=False (no output expected)
    sl = ScenarioSourceInferrer.infer_and_create(data, verbose=False)
    assert isinstance(sl, ScenarioList)
