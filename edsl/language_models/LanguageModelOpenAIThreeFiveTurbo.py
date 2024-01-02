import openai
from typing import Any
from edsl import CONFIG
from edsl.language_models import LanguageModel

openai.api_key = CONFIG.get("OPENAI_API_KEY")


class LanguageModelOpenAIThreeFiveTurbo(LanguageModel):
    """
    Child class of LanguageModel for interacting with OpenAI GPT-3.5 Turbo model.
    """

    # Class attributes
    _model_ = "gpt-3.5-turbo"
    _parameters_ = {
        "temperature": 0.5,
        "max_tokens": 1000,
        "top_p": 1,
        "frequency_penalty": 0,
        "presence_penalty": 0,
        "use_cache": True,
    }

    def __init__(self, **kwargs):
        self.model = self._model_
        # set parameters, with kwargs taking precedence over defaults
        self.parameters = dict({})
        for parameter, default_value in self._parameters_.items():
            if parameter in kwargs:
                self.parameters[parameter] = kwargs[parameter]
            else:
                self.parameters[parameter] = default_value
                kwargs[parameter] = default_value
        super().__init__(**kwargs)

    def execute_model_call(
        self, prompt: str, system_prompt: str = ""
    ) -> dict[str, Any]:
        """Calls the OpenAI API and returns the API response."""
        return openai.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            top_p=self.top_p,
            frequency_penalty=self.frequency_penalty,
            presence_penalty=self.presence_penalty,
        ).model_dump()

    @staticmethod
    def parse_response(raw_response: dict[str, Any]) -> str:
        """Parses the API response and returns the response text."""
        return raw_response["choices"][0]["message"]["content"]


def main():
    from edsl.language_models import LanguageModelOpenAIThreeFiveTurbo

    m = LanguageModelOpenAIThreeFiveTurbo(use_cache=False)
    m
    m.execute_model_call(prompt="How are you?")
    m.execute_model_call(
        system_prompt="Respond as if you are a human", prompt="How are you?"
    )
    raw_english = m.get_raw_response(
        system_prompt="You are pretending to be a human taking a survey. Do not break character.",
        prompt="What is your favorite color?",
    )
    print(raw_english)
    print(m.parse_response(raw_english))
    print(m.cost(raw_english))

    m = LanguageModelOpenAIThreeFiveTurbo(use_cache=True)
    response = m.execute_model_call(prompt="How are you?")
    raw_german = m.get_raw_response(
        prompt="What is your favorite color",
        system_prompt="""You pretending to be a human taking a survey. Do not break character. You only respond in German.""",
    )
    print(raw_german)
    print(m.parse_response(raw_german))
    print(m.cost(raw_german))
