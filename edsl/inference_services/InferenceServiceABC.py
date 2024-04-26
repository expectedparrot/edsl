from abc import abstractmethod, ABC
from typing import Any
import re


class InferenceServiceABC(ABC):
    """Abstract class for inference services."""

    @abstractmethod
    def available() -> list[str]:
        pass

    @abstractmethod
    def create_model():
        pass

    @staticmethod
    def to_class_name(s):
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
