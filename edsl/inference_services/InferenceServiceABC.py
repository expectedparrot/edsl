from abc import abstractmethod, ABC
import os
import re
from datetime import datetime, timedelta
from edsl.config import CONFIG


class InferenceServiceABC(ABC):
    """
    Abstract class for inference services.
    Anthropic: https://docs.anthropic.com/en/api/rate-limits
    """

    _coop_config_vars = None

    default_levels = {
        "google": {"tpm": 2_000_000, "rpm": 15},
        "openai": {"tpm": 2_000_000, "rpm": 10_000},
        "anthropic": {"tpm": 2_000_000, "rpm": 500},
    }

    def __init_subclass__(cls):
        """
        Check that the subclass has the required attributes.
        - `key_sequence` attribute determines...
        - `model_exclude_list` attribute determines...
        """
        if not hasattr(cls, "key_sequence"):
            raise NotImplementedError(
                f"Class {cls.__name__} must have a 'key_sequence' attribute."
            )
        if not hasattr(cls, "model_exclude_list"):
            raise NotImplementedError(
                f"Class {cls.__name__} must have a 'model_exclude_list' attribute."
            )

    @classmethod
    def _should_refresh_coop_config_vars(cls):
        """
        Returns True if config vars have been fetched over 24 hours ago, and False otherwise.
        """

        if cls._last_config_fetch is None:
            return True
        return (datetime.now() - cls._last_config_fetch) > timedelta(hours=24)

    @classmethod
    def _get_limt(cls, limit_type: str) -> int:
        key = f"EDSL_SERVICE_{limit_type.upper()}_{cls._inference_service_.upper()}"
        if key in os.environ:
            return int(os.getenv(key))

        if cls._coop_config_vars is None or cls._should_refresh_coop_config_vars():
            try:
                from edsl import Coop

                c = Coop()
                cls._coop_config_vars = c.fetch_rate_limit_config_vars()
                cls._last_config_fetch = datetime.now()
                if key in cls._coop_config_vars:
                    return cls._coop_config_vars[key]
            except Exception:
                cls._coop_config_vars = None
        else:
            if key in cls._coop_config_vars:
                return cls._coop_config_vars[key]

        if cls._inference_service_ in cls.default_levels:
            return int(cls.default_levels[cls._inference_service_][limit_type])

        return int(CONFIG.get(f"EDSL_SERVICE_{limit_type.upper()}_BASELINE"))

    def get_tpm(cls) -> int:
        """
        Returns the TPM for the service. If the service is not defined in the environment variables, it will return the baseline TPM.
        """
        return cls._get_limt(limit_type="tpm")

    def get_rpm(cls):
        """
        Returns the RPM for the service. If the service is not defined in the environment variables, it will return the baseline RPM.
        """
        return cls._get_limt(limit_type="rpm")

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
    pass
    # deep_infra_service = DeepInfraService("deep_infra", "DEEP_INFRA_API_KEY")
    # deep_infra_service.available()
    # m = deep_infra_service.create_model("microsoft/WizardLM-2-7B")
    # response = m().hello()
    # print(response)

    # anthropic_service = AnthropicService("anthropic", "ANTHROPIC_API_KEY")
    # anthropic_service.available()
    # m = anthropic_service.create_model("claude-3-opus-20240229")
    # response = m().hello()
    # print(response)
    # factory = OpenAIService("openai", "OPENAI_API")
    # factory.available()
    # m = factory.create_model("gpt-3.5-turbo")
    # response = m().hello()

    # from edsl import QuestionFreeText
    # results = QuestionFreeText.example().by(m()).run()

    # collection = InferenceServicesCollection([
    #     OpenAIService,
    #     AnthropicService,
    #     DeepInfraService
    # ])

    # available = collection.available()
    # factory = collection.create_model_factory(*available[0])
    # m = factory()
    # from edsl import QuestionFreeText
    # results = QuestionFreeText.example().by(m).run()
    # print(results)
