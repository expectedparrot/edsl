from typing import List, Optional
from ..utilities.remove_edsl_version import remove_edsl_version


class ChangeInstruction:
    def __init__(
        self,
        keep: Optional[List[str]] = None,
        drop: Optional[List[str]] = None,
    ):
        if keep is None and drop is None:
            from .exceptions import InstructionValueError

            raise InstructionValueError("Keep and drop cannot both be None")

        self.keep = keep or []
        self.drop = drop or []
        self.pseudo_index = 0.0

    def include_instruction(self, instruction_name) -> bool:
        return (instruction_name in self.keep) or (instruction_name not in self.drop)

    def add_name(self, index) -> None:
        self.name = "change_instruction_{}".format(index)

    def __str__(self):
        return self.text

    def __eq__(self, other):
        """Compare change instructions by name."""
        if not isinstance(other, ChangeInstruction):
            return False
        return getattr(self, "name", None) == getattr(other, "name", None)

    def to_dict(self, add_edsl_version=True):
        d = {
            "keep": self.keep,
            "drop": self.drop,
            "edsl_class_name": "ChangeInstruction",
        }
        # Include name if it exists
        if hasattr(self, "name"):
            d["name"] = self.name
        if add_edsl_version:
            from .. import __version__

            d["edsl_version"] = __version__
        return d

    def __hash__(self) -> int:
        """Return a hash of the question."""
        from ..utilities.utilities import dict_hash

        return dict_hash(self.to_dict(add_edsl_version=False))

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data):
        instance = cls(data.get("keep"), data.get("drop"))
        if "name" in data:
            instance.name = data["name"]
        return instance
