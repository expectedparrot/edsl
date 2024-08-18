from typing import List, Optional


class ChangeInstruction:

    def __init__(
        self,
        keep: Optional[List[str]] = None,
        drop: Optional[List[str]] = None,
    ):
        if keep is None and drop is None:
            raise ValueError("Keep and drop cannot both be None")

        self.keep = keep or []
        self.drop = drop or []

    def include_instruction(self, instruction_name) -> bool:
        return (instruction_name in self.keep) or (not instruction_name in self.drop)

    def add_name(self, index) -> None:
        self.name = "change_instruction_{}".format(index)

    def __str__(self):
        return self.text

    def to_dict(self):
        return {"keep": self.keep, "drop": self.drop}

    @classmethod
    def from_dict(cls, data):
        return cls(data["keep"], data["drop"])
