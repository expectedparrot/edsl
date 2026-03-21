from __future__ import annotations
from ..utilities import remove_edsl_version
from ..base import RepresentationMixin
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..surveys import Survey


class Instruction(RepresentationMixin):
    # CAS store support
    _store_class_name = "Instruction"
    from edsl.base.store_accessor import StoreDescriptor
    store = StoreDescriptor()

    def __init__(
        self, name, text, preamble="You were given the following instructions:"
    ):
        self.name = name
        self.text = text
        self.preamble = preamble
        self.pseudo_index = 0.0

    def __str__(self):
        return self.text

    def __repr__(self):
        return """Instruction(name="{}", text="{}")""".format(self.name, self.text)

    @classmethod
    def example(cls) -> "Instruction":
        return cls(name="example", text="This is an example instruction.")

    def to_dict(self, add_edsl_version=True):
        d = {
            "name": self.name,
            "text": self.text,
            "edsl_class_name": "Instruction",
            "preamble": self.preamble,
        }
        if add_edsl_version:
            from .. import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = "Instruction"
        return d

    def add_question(self, question) -> "Survey":
        from ..surveys import Survey

        return Survey([self, question])

    def __hash__(self) -> int:
        """Return a hash of the question."""
        from ..utilities.utilities import dict_hash

        return dict_hash(self.to_dict(add_edsl_version=False))

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data):
        return cls(
            data["name"],
            data["text"],
            data.get("preamble", "You were given the following instructions:"),
        )

    def to_yaml(self, add_edsl_version=False, filename=None):
        """Serialize to YAML.

        >>> i = Instruction(name="be_concise", text="Be brief.")
        >>> "be_concise" in i.to_yaml()
        True
        """
        import yaml

        output = yaml.dump(self.to_dict(add_edsl_version=add_edsl_version))
        if filename:
            with open(filename, "w") as f:
                f.write(output)
            return None
        return output

    @classmethod
    def from_yaml(cls, yaml_str: str) -> "Instruction":
        """Deserialize from YAML produced by :meth:`to_yaml`.

        >>> i = Instruction(name="be_concise", text="Be brief.")
        >>> i2 = Instruction.from_yaml(i.to_yaml())
        >>> i2.name == i.name and i2.text == i.text
        True
        """
        import yaml

        return cls.from_dict(yaml.safe_load(yaml_str))

    def to_jsonl(self, blob_writer=None, **kwargs) -> str:
        """Serialize to JSONL with one line per field.

        >>> import json
        >>> i = Instruction(name="be_concise", text="Be brief.")
        >>> json.loads(i.to_jsonl().splitlines()[0])["__header__"]
        True
        """
        import json
        import edsl

        d = self.to_dict(add_edsl_version=False)
        header = {
            "__header__": True,
            "edsl_class_name": "Instruction",
            "edsl_version": edsl.__version__,
        }
        lines = [json.dumps(header)]
        for field, value in d.items():
            lines.append(json.dumps({"field": field, "value": value}))
        return "\n".join(lines)

    def to_jsonl_rows(self, blob_writer=None):
        return iter(self.to_jsonl().splitlines())

    @classmethod
    def from_jsonl(cls, source, blob_reader=None, **kwargs) -> "Instruction":
        """Deserialize from JSONL produced by :meth:`to_jsonl`.

        >>> i = Instruction(name="be_concise", text="Be brief.")
        >>> i2 = Instruction.from_jsonl(i.to_jsonl())
        >>> i2.name == i.name and i2.text == i.text
        True
        """
        import json

        if isinstance(source, str):
            lines = source.strip().splitlines()
        else:
            lines = list(source)
        fields = {}
        for line in lines[1:]:
            row = json.loads(line)
            fields[row["field"]] = row["value"]
        return cls.from_dict(fields)


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
