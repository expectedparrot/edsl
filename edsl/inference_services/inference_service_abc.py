from abc import abstractmethod, ABC
import re
from datetime import datetime, timedelta


class InferenceServiceABC(ABC):
    """
    Abstract class for inference services.
    """

    _coop_config_vars = None

    def __init_subclass__(cls):
        """
        Check that the subclass has the required attributes.
        - `key_sequence` attribute determines...
        - `model_exclude_list` attribute determines...
        """
        must_have_attributes = [
            "key_sequence",
            "model_exclude_list",
            "usage_sequence",
            "input_token_name",
            "output_token_name",
            #"available_models_url",
        ]
        for attr in must_have_attributes:
            if not hasattr(cls, attr):
                from .exceptions import InferenceServiceNotImplementedError
                raise InferenceServiceNotImplementedError(
                    f"Class {cls.__name__} must have a '{attr}' attribute."
                )

    @property
    def service_name(self):
        return self._inference_service_

    @classmethod
    def _should_refresh_coop_config_vars(cls):
        """
        Returns True if config vars have been fetched over 24 hours ago, and False otherwise.
        """

        if cls._last_config_fetch is None:
            return True
        return (datetime.now() - cls._last_config_fetch) > timedelta(hours=24)

    @abstractmethod
    def available() -> list[str]:
        """
        Returns a list of available models for the service.
        """
        pass

    @abstractmethod
    def create_model():
        """
        Returns a LanguageModel object.
        """
        pass

    @staticmethod
    def to_class_name(s):
        """
        Converts a string to a valid class name.

        >>> InferenceServiceABC.to_class_name("hello world")
        'HelloWorld'
        """

        s = re.sub(r"[^a-zA-Z0-9 ]", "", s)
        s = "".join(word.title() for word in s.split())
        if s and s[0].isdigit():
            s = "Class" + s
        return s


if __name__ == "__main__":
    import doctest

    doctest.testmod()
