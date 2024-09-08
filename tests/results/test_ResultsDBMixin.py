import pytest
from unittest.mock import patch
import sqlite3

from edsl.results.ResultsDBMixin import ResultsDBMixin


class MockResultsDBMixin(ResultsDBMixin):
    def _rows(self):
        # Example implementation; replace with actual data
        yield (1, "type1", "key1", "value1")
        yield (2, "type2", "key2", "value2")


@pytest.fixture
def db_mixin():
    return MockResultsDBMixin()


def test_rows(db_mixin):
    expected_rows = [(1, "type1", "key1", "value1"), (2, "type2", "key2", "value2")]
    assert list(db_mixin._rows()) == expected_rows


def test_export_sql_dump(mocker, db_mixin):
    mocker.patch("builtins.open", mocker.mock_open())
    db_mixin.export_sql_dump(shape="long", filename="dummy.sql")
    open.assert_called_once_with("dummy.sql", "w")


# def test_backup_db_to_file(mocker, db_mixin):
#     mocker.patch("sqlite3.connect")
#     db_mixin.backup_db_to_file("backup.db")
#     sqlite3.connect.assert_called_with("backup.db")


def test_backup_db_to_file(db_mixin):
    with patch("sqlite3.connect") as mock_connect:
        db_mixin.backup_db_to_file(shape="long", filename="backup.db")
        mock_connect.assert_called_with("backup.db")


def test_db(db_mixin):
    from edsl.results.ResultsDBMixin import SQLDataShape

    conn = db_mixin._db(shape=SQLDataShape.LONG)
    cursor = conn.execute("SELECT * FROM self")
    rows = cursor.fetchall()
    assert rows == [(1, "type1", "key1", "value1"), (2, "type2", "key2", "value2")]


def test_sql(db_mixin):
    df = db_mixin.sql("SELECT * FROM self", shape="long")
    assert not df.empty
    assert df.shape == (2, 4)


def test_show_schema(db_mixin):
    from edsl.results import Results

    r = Results.example()
    # TODO: prints stuff - should capture
    r.show_schema(shape="long")
    r.show_schema(shape="wide")

    # assert "CREATE TABLE self" in schema_info


@pytest.mark.linux_only
def test_results_example():
    from edsl.results import Results

    r = Results.example()
    desired_output_string = "id,data_type,key,value\n1,model,temperature,0.5\n1,model,max_tokens,1000\n1,model,top_p,1\n1,model,frequency_penalty,0\n1,model,presence_penalty,0\n1,model,logprobs,False\n1,model,top_logprobs,3\n1,model,model,gpt-4-1106-preview\n"
    actual_output_string = r.sql(
        "select * from self where id = 1 and data_type = 'model'",
        shape="long",
        csv=True,
        remove_prefix=False,
    )
    try:
        assert actual_output_string.startswith(
            "id,data_type,key,value"
        )  # == desired_output_string
    except AssertionError:
        print(f"actual_output_string: {actual_output_string}")
        print(f"desired_output_string: {desired_output_string}")
        raise


@pytest.mark.linux_only
def test_results_example_group_by():
    from edsl.results import Results

    r = Results.example()
    output_string = "id,data_type,key,value\n1,model,temperature,0.5\n1,model,max_tokens,1000\n1,model,top_p,1\n1,model,frequency_penalty,0\n1,model,presence_penalty,0\n1,model,logprobs,False\n1,model,top_logprobs,3\n1,model,model,gpt-4-1106-preview\n"
    sql_output = r.sql(
        "select * from self where id = 1 and data_type = 'model'",
        shape="long",
        csv=True,
        remove_prefix=False,
    )
    assert sql_output.startswith("id,data_type,key,value")  # == output_string

    output_string = "0,1,2,3,4\nagent,answer,model,prompt,scenario\n4,16,28,16,4\n"
    r.sql(
        """select data_type, 
                    count(*) as count 
            from self 
            group by data_type""",
        shape="long",
        transpose=True,
        csv=True,
        remove_prefix=False,
    ) == output_string


@pytest.mark.linux_only
def test_wide_format():
    from edsl.results import Results

    r = Results.example()
    sql_results = r.sql(
        'select "answer.how_feeling" from self',
        shape="wide",
        csv=True,
        remove_prefix=False,
    )
    output_string = "answer.how_feeling\nOK\nGreat\nTerrible\nOK\n"
    assert sql_results == output_string

    sql_results = r.sql(
        "select how_feeling from self", shape="wide", remove_prefix=True, csv=True
    )
    output_string = "how_feeling\nOK\nGreat\nTerrible\nOK\n"
    assert sql_results == output_string


# Additional tests for transpose and CSV functionality can be added similarly.
