import difflib
from typing import Any, Dict, Tuple
from collections import UserList

class BaseDiffCollection(UserList):
    def __init__(self, diffs=None):
        if diffs is None:
            diffs = []
        super().__init__(diffs)

    def apply(self, obj: Any):
        for diff in self:
            obj = diff.apply(obj)
        return obj
    
    def add_diff(self, diff) -> 'BaseDiffCollection':
        self.append(diff)
        return self

class BaseDiff:
    def __init__(self, obj1: Any, obj2: Any, added=None, removed=None, modified=None):
        # if type(obj1) != type(obj2):
        #     raise ValueError("Objects must be of the same class", 
        #                      "obj1 is of type", type(obj1).__name__,
        #                      "obj2 is of type", type(obj2).__name__
        #                      )

        self.obj1 = obj1
        self.obj2 = obj2
        self._dict1 = obj1._to_dict()
        self._dict2 = obj2._to_dict()
        self._obj_class = type(obj1)
        
        self.added = added
        self.removed = removed
        self.modified = modified

    def __bool__(self):
        return bool(self.added or self.removed or self.modified)

    @property
    def added(self):
        if self._added is None:
            self._added = self._find_added()
        return self._added
    
    def __add__(self, other):
        return self.apply(other)

    @added.setter
    def added(self, value):
        self._added = value if value is not None else self._find_added()

    @property
    def removed(self):
        if self._removed is None:
            self._removed = self._find_removed()
        return self._removed

    @removed.setter
    def removed(self, value):
        self._removed = value if value is not None else self._find_removed()

    @property
    def modified(self):
        if self._modified is None:
            self._modified = self._find_modified()
        return self._modified

    @modified.setter
    def modified(self, value):
        self._modified = value if value is not None else self._find_modified()

    def _find_added(self) -> Dict[Any, Any]:
        return {k: self._dict2[k] for k in self._dict2 if k not in self._dict1}

    def _find_removed(self) -> Dict[Any, Any]:
        return {k: self._dict1[k] for k in self._dict1 if k not in self._dict2}

    def _find_modified(self) -> Dict[Any, Tuple[Any, Any, str]]:
        modified = {}
        for k in self._dict1:
            if k in self._dict2 and self._dict1[k] != self._dict2[k]:
                if isinstance(self._dict1[k], str) and isinstance(self._dict2[k], str):
                    diff = self._diff_strings(self._dict1[k], self._dict2[k])
                    modified[k] = (self._dict1[k], self._dict2[k], diff)
                else:
                    modified[k] = (self._dict1[k], self._dict2[k], "")
        return modified

    def _diff_strings(self, str1: str, str2: str) -> str:
        diff = difflib.ndiff(str1.splitlines(), str2.splitlines())
        return '\n'.join(diff)

    def apply(self, obj: Any):
        """Apply the diff to the object."""
        # if type(obj) != self._obj_class:
        #     raise ValueError("Object must be of the same class used for the diff")
        
        new_obj_dict = obj._to_dict()
        for k, v in self.added.items():
            new_obj_dict[k] = v
        for k in self.removed.keys():
            del new_obj_dict[k]
        for k, (v1, v2, diff) in self.modified.items():
            new_obj_dict[k] = v2

        return obj.from_dict(new_obj_dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'added': self.added,
            'removed': self.removed,
            'modified': self.modified,
            'obj1': self._dict1,
            'obj2': self._dict2,
            'obj_class': self._obj_class.__name__
        }

    @classmethod
    def from_dict(cls, diff_dict: Dict[str, Any], obj1: Any, obj2: Any):
        # if diff_dict['obj_class'] != type(obj1).__name__ or diff_dict['obj_class'] != type(obj2).__name__:
        #     raise ValueError("Objects must be of the same class as in the diff dict")
        
        return cls(
            obj1=obj1,
            obj2=obj2,
            added=diff_dict['added'],
            removed=diff_dict['removed'],
            modified=diff_dict['modified']
        )

    def __str__(self):
        result = []
        if self.added:
            result.append("Added keys and values:")
            for k, v in self.added.items():
                result.append(f"  {k}: {v}")
        if self.removed:
            result.append("Removed keys and values:")
            for k, v in self.removed.items():
                result.append(f"  {k}: {v}")
        if self.modified:
            result.append("Modified keys and values:")
            for k, (v1, v2, diff) in self.modified.items():
                result.append(f"  {k}:")
                result.append(f"    Old value: {v1}")
                result.append(f"    New value: {v2}")
                if diff:
                    result.append(f"    Diff:\n{diff}")
        return '\n'.join(result)
    
    def __repr__(self):
        return (f"DictDiff(obj1={self.obj1!r}, obj2={self.obj2!r}, added={self.added!r}, "
                f"removed={self.removed!r}, modified={self.modified!r})")
    
    def add_diff(self, diff) -> 'BaseDiffCollection':
        return BaseDiffCollection([self, diff])


if __name__ == "__main__":
    from edsl import Question
    q_ft = Question.example("free_text")
    q_mc = Question.example("multiple_choice")

    diff1 = q_ft - q_mc
    assert q_ft == q_mc + diff1
    assert q_ft == diff1.apply(q_mc)
    # new_q_mc = diff1.apply(q_ft)
    # assert new_q_mc == q_mc

    # new_q_mc = q_ft + diff1
    # assert new_q_mc == q_mc

    # new_q_mc = diff1 + q_ft
    # assert new_q_mc == q_mc

    # ## Test chain of diffs
    q0 = Question.example("free_text")
    q1 = q0.copy()
    q1.question_text = "Why is Buzzard's Bay so named?"
    diff1 = q1 - q0
    q2 = q1.copy()
    q2.question_name = "buzzard_bay"
    diff2 = q2 - q1

    diff_chain = diff1.add_diff(diff2)

    new_q2 = diff_chain.apply(q0)
    assert new_q2 == q2

    new_q2 = diff_chain + q0
    assert new_q2 == q2



    # new_diffs = diff1.add_diff(diff1).add_diff(diff1)
    # assert len(new_diffs) == 3


    # q0 = Question.example("free_text")
    # q1 = Question.example("free_text")
    # q1.question_text = "Why is Buzzard's Bay so named?"
    # q2 = q1.copy()



