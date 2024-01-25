from collections import UserDict


class DAG(UserDict):
    def __init__(self, data: dict):
        self.data = data
        self.reverse_mapping = self._create_reverse_mapping()

    def _create_reverse_mapping(self):
        rev_map = {}
        for key, values in self.data.items():
            for value in values:
                rev_map.setdefault(value, set()).add(key)
        return rev_map

    def get_all_children(self, key):
        children = set()

        def dfs(node):
            for child in self.reverse_mapping.get(node, []):
                if child not in children:
                    children.add(child)
                    dfs(child)

        dfs(key)
        return children
