import time
from typing import Any, Optional, Dict


class ObjectEntry:
    """
    ObjectEntry is a class that represents an object that is created in EDSL.
    - It is used to store information about the object, such as its name, description, and creation time.
    - It also has a method to push the object to the Coop, and a method to view the object on the Coop.
    """

    def __init__(
        self,
        variable_name: str,
        object: Any,
        description: str,
        coop_info: Optional[Dict[str, Any]] = None,
        created_at: Optional[float] = None,
        edsl_class_name: Optional[str] = None,
    ):
        self.created_at = created_at or time.time()
        self.variable_name = variable_name
        self.object = object
        self.edsl_class_name = edsl_class_name or object.__class__.__name__
        self.description = description
        self.coop_info = coop_info

    @classmethod
    def _get_class(self, obj_dict: dict) -> type:
        """
        Get the class of an object from its dictionary representation.
        """
        class_name = obj_dict["edsl_class_name"]
        if class_name == "QuestionBase":
            from edsl import QuestionBase

            return QuestionBase
        else:
            from edsl.Base import RegisterSubclassesMeta

            return RegisterSubclassesMeta._registry[class_name]

    def __repr__(self) -> str:
        """
        Return a string representation of the ObjectEntry instance.
        """
        return f"ObjectEntry(variable_name='{self.variable_name}', object={self.object!r}, description='{self.description}', coop_info={self.coop_info}, created_at={self.created_at}, edsl_class_name='{self.edsl_class_name}')"

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the ObjectEntry instance to a dictionary.
        """
        return {
            "created_at": self.created_at,
            "variable_name": self.variable_name,
            "object": self.object.to_dict(),
            "edsl_class_name": self.edsl_class_name,
            "description": self.description,
            "coop_info": self.coop_info,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ObjectEntry":
        """
        Create an ObjectEntry instance from a dictionary.
        """
        d["object"] = cls._get_class(d["object"]).from_dict(d["object"])
        return cls(**d)

    @property
    def hash(self) -> str:
        """
        Return a hash of the object.
        """
        return str(hash(self.object))

    def add_to_namespace(self) -> None:
        """
        Add the object to the global namespace using its variable name.
        """
        globals()[self.variable_name] = self.object

    @property
    def coop_info(self) -> Optional[Dict[str, Any]]:
        """
        Get Coop information for the object.
        """
        return self._coop_info

    @coop_info.setter
    def coop_info(self, coop_info: Optional[Dict[str, Any]]) -> None:
        """
        Set Coop information for the object.
        """
        self._coop_info = coop_info

    def view_on_coop(self) -> None:
        """
        Open the coop URL in a web browser if available.
        """
        if self.coop_info is None:
            print("Object not pushed to coop")
            return
        url = self.coop_info["url"]
        import webbrowser

        webbrowser.open(url)

    def push(self, refresh: bool = False) -> None:
        """
        Push the object to the Coop.
        """
        if self.coop_info is None or refresh:
            self.coop_info = self.object.push(description=self.description)
            print(
                f"Object {self.variable_name} pushed to coop with info: {self._coop_info}"
            )
        else:
            print(
                f"Object {self.variable_name} already pushed to coop with info: {self._coop_info}"
            )


if __name__ == "__main__":
    from edsl import QuestionFreeText

    q = QuestionFreeText.example()

    oe = ObjectEntry("q", q, "This is a question")
    d = oe.to_dict()
    new_oe = ObjectEntry.from_dict(d)
    # print(oe.coop_info)
