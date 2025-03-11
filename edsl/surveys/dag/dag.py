"""Directed Acyclic Graph (DAG) class."""

from collections import UserDict
from graphlib import TopologicalSorter


class DAG(UserDict):
    """Class for creating a Directed Acyclic Graph (DAG) from a dictionary."""

    def __init__(self, data: dict):
        """Initialize the DAG class."""
        super().__init__(data)
        self.reverse_mapping = self._create_reverse_mapping()
        self.validate_no_cycles()

    def _create_reverse_mapping(self) -> dict:
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

    def get_all_children(self, key) -> set:
        """Get all children of a node in the DAG."""
        children = set()

        def dfs(node):
            for child in self.reverse_mapping.get(node, []):
                if child not in children:
                    children.add(child)
                    dfs(child)

        dfs(key)
        return children

    def topologically_sorted_nodes(self) -> list[str]:
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

    def __add__(self, other_dag: 'DAG') -> 'DAG':
        """Combine two DAGs.
        
        >>> from edsl.surveys.dag import DAG
        >>> dag1 = DAG({'a': {'b'}, 'b': {'c'}})
        >>> dag2 = DAG({'d': {'e'}, 'e': {'f'}})
        >>> dag1 + dag2 ==  {'d': {'e'}, 'a': {'b'}, 'e': {'f'}, 'b': {'c'}}
        True
        """
        d = {}
        combined_keys = set(self.keys()).union(set(other_dag.keys()))
        for key in combined_keys:
            d[key] = set(self.get(key, set({}))).union(set(other_dag.get(key, set({}))))
        return DAG(d)

    def remove_node(self, node: int) -> None:
        """Remove a node and all its connections from the DAG."""
        self.pop(node, None)
        for connections in self.values():
            connections.discard(node)
        # Adjust remaining nodes if necessary
        self._adjust_nodes_after_removal(node)

    def _adjust_nodes_after_removal(self, removed_node: int) -> None:
        """Adjust node indices after a node is removed."""
        new_dag = {}
        for node, connections in self.items():
            new_node = node if node < removed_node else node - 1
            new_connections = {c if c < removed_node else c - 1 for c in connections}
            new_dag[new_node] = new_connections
        self.clear()
        self.update(new_dag)

    @classmethod
    def example(cls):
        """Return an example of the `DAG`."""
        data = {"a": ["b", "c"], "b": ["d"], "c": [], "d": []}
        return cls(data)

    def detect_cycles(self):
        """
        Detect cycles in the DAG using depth-first search.

        :return: A list of cycles if any are found, otherwise an empty list.
        """
        visited = set()
        path = []
        cycles = []

        def dfs(node):
            if node in path:
                cycle = path[path.index(node) :]
                cycles.append(cycle + [node])
                return

            if node in visited:
                return

            visited.add(node)
            path.append(node)

            for child in self.get(node, []):
                dfs(child)

            path.pop()

        for node in self:
            if node not in visited:
                dfs(node)

        return cycles

    def validate_no_cycles(self):
        """
        Validate that the DAG does not contain any cycles.

        :raises ValueError: If cycles are detected in the DAG.
        """
        cycles = self.detect_cycles()
        if cycles:
            raise ValueError(f"Cycles detected in the DAG: {cycles}")


if __name__ == "__main__":
    import doctest

    doctest.testmod()
