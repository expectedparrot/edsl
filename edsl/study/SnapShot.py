from typing import Generator
import inspect


class SnapShot:
    def __init__(self, namespace, exclude=None):
        if exclude is None:
            self.exclude = []
        else:
            self.exclude = exclude

        self.edsl_objects = dict(self._get_edsl_objects(namespace=namespace))
        self.edsl_classes = dict(self._get_edsl_classes(namespace=namespace))

    def __repr__(self):
        return f"SnapShot(edsl_objects={self.edsl_objects}, edsl_classes={self.edsl_objects})"

    def _get_edsl_classes(
        self, namespace: dict
    ) -> Generator[tuple[str, type], None, None]:
        """Get all EDSL classes in the namespace.

        :param namespace: The namespace to search for EDSL classes. The default is the global namespace.

        >>> sn = SnapShot(namespace = {})
        >>> sn.edsl_classes
        {}

        >>> from edsl.data.Cache import Cache
        >>> sn = SnapShot(namespace = globals())
        >>> sn.edsl_classes
        {'Cache': <class 'edsl.data.Cache.Cache'>}
        """
        from edsl.Base import RegisterSubclassesMeta
        from edsl import QuestionBase

        all_edsl_objects = RegisterSubclassesMeta.get_registry()

        for name, value in namespace.items():
            if (
                inspect.isclass(value)
                and name in all_edsl_objects
                and value != RegisterSubclassesMeta
            ):
                yield name, value
            if inspect.isclass(value) and issubclass(value, QuestionBase):
                yield name, value

    def _get_edsl_objects(self, namespace) -> Generator[tuple[str, type], None, None]:
        """Get all EDSL objects in the global namespace.

        >>> sn = SnapShot(namespace = globals())
        >>> sn.edsl_objects
        {}

        """
        from edsl.Base import Base
        from edsl.study.Study import Study

        for name, value in namespace.items():
            if (
                hasattr(value, "to_dict")
                and not inspect.isclass(value)
                and value not in self.exclude
            ):
                yield name, value


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
