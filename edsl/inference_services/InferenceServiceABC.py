from abc import abstractmethod, ABC
import os
import re
from edsl.config import CONFIG


class InferenceServiceABC(ABC):
    """
    Abstract class for inference services.
    """

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

    def get_tpm(cls) -> int:
        """
        Returns the TPM for the service. If the service is not defined in the environment variables, it will return the baseline TPM.
        """
        key = f"EDSL_SERVICE_TPM_{cls._inference_service_.upper()}"
        tpm = os.getenv(key) or CONFIG.get("EDSL_SERVICE_TPM_BASELINE")
        return int(tpm)

    def get_rpm(cls):
        """
        Returns the RPM for the service. If the service is not defined in the environment variables, it will return the baseline RPM.
        """
        key = f"EDSL_SERVICE_RPM_{cls._inference_service_.upper()}"
        rpm = os.getenv(key) or CONFIG.get("EDSL_SERVICE_RPM_BASELINE")
        return int(rpm)

    @abstractmethod
    def available() -> list[str]:
        pass

    @abstractmethod
    def create_model():
        pass

    @staticmethod
    def to_class_name(s):
        """Convert a string to a valid class name.

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
