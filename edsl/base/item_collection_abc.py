from typing import List, Optional, Dict
from collections import UserList
import uuid


class ItemCollection(UserList):
    """Abstract base class for managing collections of items.

    This class extends UserList to provide additional functionality for managing
    named collections of items. It includes methods for naming items, selecting
    and dropping items by name, and serialization/deserialization.

    Attributes:
        item_class: The class type of items stored in this collection (set by subclasses).
        name: The name of this collection.

    Examples:
        >>> # This is an abstract base class, typically used through subclasses
        >>> class MyItem:
        ...     def __init__(self, value):
        ...         self.value = value
        ...         self.name = None
        ...     def to_dict(self):
        ...         return {'value': self.value, 'name': self.name}
        ...     @classmethod
        ...     def from_dict(cls, data):
        ...         item = cls(data['value'])
        ...         item.name = data['name']
        ...         return item
        >>> class MyCollection(ItemCollection):
        ...     item_class = MyItem
        >>> items = [MyItem(1), MyItem(2)]
        >>> collection = MyCollection(items, name="test_collection")
        >>> len(collection)
        2
    """

    item_class: None

    def __init__(
        self,
        *args,
        name: Optional[str] = None,
        names: Optional[List[str]] = None,
        override: bool = False,
        **kwargs,
    ):
        """Initialize an ItemCollection.

        Args:
            *args: Items to include in the collection.
            name: Optional name for the collection. If None, generates a unique name.
            names: Optional list of names to assign to items in the collection.
            override: If True, override existing item names. If False, preserve existing names.
            **kwargs: Additional arguments passed to UserList.__init__.

        Examples:
            >>> class Item:
            ...     def __init__(self, value):
            ...         self.value = value
            ...         self.name = None
            >>> class TestCollection(ItemCollection):
            ...     item_class = Item
            >>> items = [Item(1), Item(2)]
            >>> collection = TestCollection(items, name="my_collection")
            >>> collection.name
            'my_collection'
        """
        super().__init__(*args, **kwargs)
        if name is not None:
            self.name = name
        else:
            self.name = self.__class__.__name__ + "_" + str(uuid.uuid4())
        self.give_names(names, override)

    def __repr__(self):
        """Return a string representation of the collection.

        Returns:
            str: A multi-line string showing the collection name and items.

        Examples:
            >>> class Item:
            ...     def __init__(self, value):
            ...         self.value = value
            ...         self.name = f"item_{value}"
            ...     def __len__(self):
            ...         return 1
            >>> class TestCollection(ItemCollection):
            ...     item_class = Item
            >>> items = [Item(1), Item(2)]
            >>> collection = TestCollection(items, name="test_collection")
            >>> "List of Item objects with name test_collection" in repr(collection)
            True
        """
        lines = [f"List of {self.item_class.__name__} objects with name {self.name}"]
        for item in self:
            try:
                length = f"{len(item)} items"
            except (TypeError, AttributeError):
                length = ""
            lines.append(f"  {item.name} ({item.__class__.__name__}); {length}")
        return "\n".join(lines)

    def __add__(self, other):
        """Add two collections together.

        Args:
            other: Another ItemCollection to add to this one.

        Returns:
            ItemCollection: A new collection containing items from both collections.

        Examples:
            >>> class Item:
            ...     def __init__(self, value):
            ...         self.value = value
            ...         self.name = f"item_{value}"
            >>> class TestCollection(ItemCollection):
            ...     item_class = Item
            >>> collection1 = TestCollection([Item(1)], name="first")
            >>> collection2 = TestCollection([Item(2)], name="second")
            >>> combined = collection1 + collection2
            >>> len(combined)
            2
            >>> combined.name
            'first + second'
        """
        return self.__class__(
            list(self) + list(other), name=self.name + " + " + other.name
        )

    def generate_combinations(self, length: int) -> List[str]:
        """Generates all combinations of the item names of length `length`"""
        from itertools import combinations

        if length > len(self.item_names):
            raise ValueError(
                f"Length {length} is greater than the number of items in the collection {len(self.item_names)}"
            )
        return list(combinations(self.item_names, length))

    def generate_all_combinations(self) -> List[str]:
        """Generates all combinations of the item names of length `length`"""
        combos = []
        for k in range(1, len(self.item_names) + 1):
            for combo in self.generate_combinations(k):
                combos.extend(combo)
        return combos

    def give_names(self, names: Optional[List[str]] = None, override: bool = False):
        """Assign names to items in the collection.

        Args:
            names: List of names to assign. If None, generates names based on hash.
            override: If True, override existing names. If False, only name items without names.

        Raises:
            AssertionError: If the number of names doesn't match the number of items.

        Examples:
            >>> class Item:
            ...     def __init__(self, value):
            ...         self.value = value
            ...         self.name = None
            >>> class TestCollection(ItemCollection):
            ...     item_class = Item
            >>> items = [Item(1), Item(2)]
            >>> collection = TestCollection(items)
            >>> collection.give_names(["first", "second"], override=True)
            >>> collection[0].name
            'first'
            >>> collection[1].name
            'second'
        """
        if names is None:
            names = [self.__class__.__name__ + "_" + str(hash(item)) for item in self]

        assert len(names) == len(self), "Number of names must match number of items"
        for item, name in zip(self, names):
            if override or (hasattr(item, "name") and item.name is None):
                item.name = name
            else:
                pass

    @property
    def item_names(self):
        """Get a list of all item names in the collection.

        Returns:
            List[str]: List of item names. Uses generated names for items without names.

        Examples:
            >>> class Item:
            ...     def __init__(self, value):
            ...         self.value = value
            ...         self.name = f"item_{value}"
            >>> class TestCollection(ItemCollection):
            ...     item_class = Item
            >>> items = [Item(1), Item(2)]
            >>> collection = TestCollection(items)
            >>> names = collection.item_names
            >>> len(names)
            2
            >>> all(name.startswith("item_") for name in names)
            True
        """
        names = []
        for item in self:
            if hasattr(item, "name") and item.name is not None:
                names.append(item.name)
            else:
                names.append(item.__class__.__name__ + "_" + str(hash(item)))
        return names

    def select(self, *select_item_names: List[str]) -> "ItemCollection":
        """Select items from the collection by name.

        Args:
            *select_item_names: Names of items to select.

        Returns:
            ItemCollection: A new collection containing only the selected items.

        Raises:
            ValueError: If no items are found with the given names.

        Examples:
            >>> class Item:
            ...     def __init__(self, value):
            ...         self.value = value
            ...         self.name = f"item_{value}"
            >>> class TestCollection(ItemCollection):
            ...     item_class = Item
            >>> items = [Item(1), Item(2), Item(3)]
            >>> collection = TestCollection(items)
            >>> selected = collection.select("item_1", "item_3")
            >>> len(selected)
            2
        """
        new_list = self.__class__(
            [item for item in self if item.name in select_item_names]
        )
        if len(new_list) == 0:
            raise ValueError(
                f"No items found in {self.name} with names {select_item_names}",
                "Valid names are: " + ", ".join(self.item_names),
            )
        return new_list

    def drop(self, *drop_item_names: List[str]) -> "ItemCollection":
        """Drop items from the collection by name.

        Args:
            *drop_item_names: Names of items to drop.

        Returns:
            ItemCollection: A new collection with the specified items removed.

        Raises:
            ValueError: If no items remain after dropping.

        Examples:
            >>> class Item:
            ...     def __init__(self, value):
            ...         self.value = value
            ...         self.name = f"item_{value}"
            >>> class TestCollection(ItemCollection):
            ...     item_class = Item
            >>> items = [Item(1), Item(2), Item(3)]
            >>> collection = TestCollection(items)
            >>> remaining = collection.drop("item_2")
            >>> len(remaining)
            2
        """
        new_list = self.__class__(
            [item for item in self if item.name not in drop_item_names]
        )
        if len(new_list) == 0:
            raise ValueError(
                f"No items found in {self.name} with names {drop_item_names}",
                "Valid names are: " + ", ".join(self.item_names),
            )
        return new_list

    def to_dict(self):
        """Convert the collection to a dictionary representation.

        Returns:
            Dict: Dictionary with 'items' key containing list of item dictionaries.

        Examples:
            >>> class Item:
            ...     def __init__(self, value):
            ...         self.value = value
            ...         self.name = f"item_{value}"
            ...     def to_dict(self):
            ...         return {'value': self.value, 'name': self.name}
            >>> class TestCollection(ItemCollection):
            ...     item_class = Item
            >>> items = [Item(1), Item(2)]
            >>> collection = TestCollection(items)
            >>> data = collection.to_dict()
            >>> 'items' in data
            True
            >>> len(data['items'])
            2
        """
        return {"items": [item.to_dict() for item in self]}

    @classmethod
    def from_dict(cls, data: Dict):
        """Create a collection from a dictionary representation.

        Args:
            data: Dictionary containing 'items' key with list of item data.

        Returns:
            ItemCollection: New collection created from the dictionary data.

        Examples:
            >>> class Item:
            ...     def __init__(self, value):
            ...         self.value = value
            ...         self.name = None
            ...     def to_dict(self):
            ...         return {'value': self.value, 'name': self.name}
            ...     @classmethod
            ...     def from_dict(cls, item_data):
            ...         item = cls(item_data['value'])
            ...         item.name = item_data['name']
            ...         return item
            >>> class TestCollection(ItemCollection):
            ...     item_class = Item
            >>> data = {'items': [{'value': 1, 'name': 'item_1'}]}
            >>> collection = TestCollection.from_dict(data)
            >>> len(collection)
            1
        """
        return cls([cls.item_class.from_dict(item) for item in data["items"]])

    def save(self, filename: Optional[str]):
        """Save the collection to a JSON file.

        Args:
            filename: Name of the file to save to. If None, uses collection name.

        Examples:
            >>> import tempfile
            >>> import os
            >>> class Item:
            ...     def __init__(self, value):
            ...         self.value = value
            ...         self.name = f"item_{value}"
            ...     def to_dict(self):
            ...         return {'value': self.value, 'name': self.name}
            >>> class TestCollection(ItemCollection):
            ...     item_class = Item
            >>> items = [Item(1)]
            >>> collection = TestCollection(items, name="test")
            >>> with tempfile.TemporaryDirectory() as tmpdir:
            ...     filepath = os.path.join(tmpdir, "test.json")
            ...     collection.save(filepath)  # doctest: +ELLIPSIS
            File written to .../test.json
        """
        import json

        if filename is None:
            filename = f"{self.name}.json"
        with open(filename, "w") as f:
            f.write(json.dumps(self.to_dict()))
        print(f"File written to {filename}")

    @classmethod
    def load(cls, filename: str):
        """Load a collection from a JSON file.

        Args:
            filename: Name of the file to load from.

        Returns:
            ItemCollection: Collection loaded from the file.

        Examples:
            >>> import tempfile
            >>> import json
            >>> import os
            >>> class Item:
            ...     def __init__(self, value):
            ...         self.value = value
            ...         self.name = None
            ...     def to_dict(self):
            ...         return {'value': self.value, 'name': self.name}
            ...     @classmethod
            ...     def from_dict(cls, item_data):
            ...         item = cls(item_data['value'])
            ...         item.name = item_data['name']
            ...         return item
            >>> class TestCollection(ItemCollection):
            ...     item_class = Item
            >>> with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            ...     json.dump({'items': [{'value': 1, 'name': 'item_1'}]}, f)
            ...     temp_filename = f.name
            >>> collection = TestCollection.load(temp_filename)
            >>> len(collection)
            1
            >>> os.unlink(temp_filename)  # Clean up
        """
        import json

        with open(filename, "r") as f:
            data = json.load(f)
        return cls.from_dict(data)


if __name__ == "__main__":
    import doctest

    doctest.testmod(verbose=True)
