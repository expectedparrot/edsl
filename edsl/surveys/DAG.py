"""Directed Acyclic Graph (DAG) class."""
from collections import UserDict
from graphlib import TopologicalSorter


class DAG(UserDict):
    """Class for creating a Directed Acyclic Graph (DAG) from a dictionary."""

    def __init__(self, data: dict):
        """Initialize the DAG class."""
        super().__init__(data)
        self.reverse_mapping = self._create_reverse_mapping()

    def _create_reverse_mapping(self):
        """
        Create a reverse mapping of the DAG, where the keys are the children and the values are the parents.

        Example usage:

        .. code-block:: python

            data = {"a": ["b", "c"], "b": ["d"], "c": [], "d": []}
            dag = DAG(data)
            dag._create_reverse_mapping()
            {'b': {'a'}, 'c': {'a'}, 'd': {'b'}}

        """
        rev_map = {}
        for key, values in self.items():
            for value in values:
                rev_map.setdefault(value, set()).add(key)
        return rev_map

    def get_all_children(self, key):
        """Get all children of a node in the DAG."""
        children = set()

        def dfs(node):
            for child in self.reverse_mapping.get(node, []):
                if child not in children:
                    children.add(child)
                    dfs(child)

        dfs(key)
        return children

    def topologically_sorted_nodes(self):
        """
        Return a sequence of the DAG.

        Example usage:

        .. code-block:: python

            data = {"a": ["b", "c"], "b": ["d"], "c": [], "d": []}
            dag = DAG(data)
            dag.topologically_sorted_nodes() == ['c', 'd', 'b', 'a']
            True

        """
        return list(TopologicalSorter(self).static_order())

    def __add__(self, other_dag):
        """Combine two DAGs."""
        d = {}
        combined_keys = set(self.keys()).union(set(other_dag.keys()))
        for key in combined_keys:
            d[key] = self.get(key, set({})).union(other_dag.get(key, set({})))
        return DAG(d)
        # if textify:
        #     return DAG(self.textify(d))
        # else:
        #     return DAG(d)

    @classmethod
    def example(cls):
        """Return an example of the `DAG`."""
        data = {"a": ["b", "c"], "b": ["d"], "c": [], "d": []}
        return cls(data)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
