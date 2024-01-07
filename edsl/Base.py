from abc import ABC, abstractmethod


class Base(ABC):
    @abstractmethod
    def example(self):
        pass

    @abstractmethod
    def to_dict():
        pass

    @abstractmethod
    def from_dict():
        pass

    @abstractmethod
    def code():
        pass

    def show_methods(self, show_docstrings=True):
        public_methods_with_docstrings = [
            (method, getattr(self, method).__doc__)
            for method in dir(self)
            if callable(getattr(self, method)) and not method.startswith("_")
        ]
        if show_docstrings:
            for method, documentation in public_methods_with_docstrings:
                print(f"{method}: {documentation}")
        else:
            return [x[0] for x in public_methods_with_docstrings]
