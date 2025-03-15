from edsl.surveys.dag import DAG


def test_dag_initialization():
    data = {"a": ["b", "c"], "b": ["d"], "c": [], "d": []}
    dag = DAG(data)
    assert dag.data == data


def test_reverse_mapping():
    data = {"a": ["b", "c"], "b": ["d"], "c": [], "d": []}
    dag = DAG(data)
    reverse_mapping = dag._create_reverse_mapping()
    expected_reverse_mapping = {"b": {"a"}, "c": {"a"}, "d": {"b"}}
    assert reverse_mapping == expected_reverse_mapping


def test_get_all_children_no_children():
    data = {"a": [], "b": [], "c": []}
    dag = DAG(data)
    children = dag.get_all_children("a")
    assert children == set()


def test_get_all_children_direct_children():
    data = {"a": ["b", "c"], "b": [], "c": []}
    dag = DAG(data)
    children = dag.get_all_children("b")
    assert children == {"a"}


def test_get_all_children_nested_children():
    data = {"a": ["b"], "b": ["c"], "c": ["d"], "d": []}
    dag = DAG(data)
    children = dag.get_all_children("a")
    assert children == set({})
