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
            return func(self, *args, **kwargs)

    wrapper._is_wrapped = True
    return wrapper


def decorate_methods_from_mixin(cls, mixin_cls):
    for attr_name, attr_value in mixin_cls.__dict__.items():
        if callable(attr_value) and not attr_name.startswith("__"):
            setattr(cls, attr_name, to_dataset(attr_value))
    return cls


class ResultsExportMixin(DatasetExportMixin):
    """Mixin class for exporting Results objects."""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        decorate_methods_from_mixin(cls, DatasetExportMixin)


if __name__ == "__main__":
    # pass
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
