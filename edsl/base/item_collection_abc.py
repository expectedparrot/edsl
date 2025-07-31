from typing import List, Optional, Dict
from collections import UserList
import uuid

class ItemCollection(UserList):

    item_class: None

    def __init__(self, *args, name : Optional[str] = None, names: Optional[List[str]] = None, override: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        if name is not None:
            self.name = name
        else:
            self.name = self.__class__.__name__ + "_" + str(uuid.uuid4())
        self.give_names(names, override)

    def __repr__(self):
        lines = [f"List of {self.item_class.__name__} objects with name {self.name}"]
        for item in self:
            try: 
                length = f'{len(item)} items'
            except:
                length = ""
            lines.append(f"  {item.name} ({item.__class__.__name__}); {length}")
        return "\n".join(lines)

    def __add__(self, other):
        return self.__class__(list(self) + list(other), name = self.name + " + " + other.name)

    def give_names(self, names: Optional[List[str]] = None, override: bool = False):
        if names is None:
            names = [self.__class__.__name__ + "_" + str(hash(item)) for item in self]

        assert len(names) == len(self), "Number of names must match number of items"
        for item, name in zip(self, names):
            if override or (hasattr(item,"name") and item.name is None):
                item.name = name    
            else:
                pass
                #print(f"Item {item} already has a name, {item.name}. Use override = True to override.")
                #raise ValueError(f"Item {item} already has a name {item.name}. Use override = True to override.")

    @property
    def item_names(self):
        names = []
        for item in self: 
            if hasattr(item, 'name') and item.name is not None:
                names.append(item.name)
            else:
                names.append(item.__class__.__name__ + "_" + str(hash(item)))
        return names

    def select(self, *select_item_names: List[str]) -> 'ItemCollection':
        new_list = self.__class__([item for item in self if item.name in select_item_names])
        if len(new_list) == 0:
            raise ValueError(f"No items found in {self.name} with names {select_item_names}", 
                             "Valid names are: " + ", ".join(self.item_names))
        return new_list
    
    def drop(self, *drop_item_names: List[str]) -> 'ItemCollection':
        new_list = self.__class__([item for item in self if item.name not in drop_item_names])
        if len(new_list) == 0:
            raise ValueError(f"No items found in {self.name} with names {drop_item_names}", 
                             "Valid names are: " + ", ".join(self.item_names))
        return new_list
    

    def to_dict(self):
        return {'items': [item.to_dict() for item in self]}
    
    @classmethod
    def from_dict(cls, data: Dict):
        return cls([cls.item_class.from_dict(item) for item in data['items']])
    
    def save(self, filename: Optional[str]):
        import json
        if filename is None:
            filename = f'{self.name}.json'
        with open(filename, 'w') as f:
            f.write(json.dumps(self.to_dict()))
        print(f"File written to {filename}")
    
    @classmethod
    def load(cls, filename: str):
        import json
        with open(filename, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)
      