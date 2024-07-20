"""Mixin class for exporting results."""
from functools import wraps
from typing import Literal, Optional, Union

from edsl.results.DatasetExportMixin import DatasetExportMixin

def to_dataset(func):
    """Convert the Results object to a Dataset object before calling the function."""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        """Return the function with the Results object converted to a Dataset object."""
        if self.__class__.__name__ == "Results":
            return func(self.select(), *args, **kwargs)
        else:
            raise Exception(
                f"Class {self.__class__.__name__} not recognized as a Results or Dataset object."
            )

    return wrapper

def decorate_all_methods(cls):
    for attr_name, attr_value in cls.__dict__.items():
        if callable(attr_value):
            setattr(cls, attr_name, to_dataset(attr_value))
    return cls


@decorate_all_methods
class ResultsExportMixin(DatasetExportMixin):
    """Mixin class for exporting Results objects."""


if __name__ == "__main__":
    #pass
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
