# import anthropic
import os
import dotenv
from typing import Any
from anthropic import AsyncAnthropic

dotenv.load_dotenv()

api_key = os.environ.get("ANTHROPIC_API_KEY")

from edsl.language_models.LanguageModel import LanguageModel
from edsl.enums import InferenceServiceType
from edsl.enums import LanguageModelType
from edsl.exceptions import MissingAPIKeyError
import os
import re


def create_anthropic_model(model_name, model_class_name) -> LanguageModel:
    class LLM(LanguageModel):
        """
        Child class of LanguageModel for interacting with OpenAI models
        """

        _inference_service_ = InferenceServiceType.ANTHROPIC.value
        _model_ = model_name
        _parameters_ = {
            "temperature": 0.5,
            "max_tokens": 1000,
            "top_p": 1,
            "frequency_penalty": 0,
            "presence_penalty": 0,
            "logprobs": False,
            "top_logprobs": 3,
        }

        async def async_execute_model_call(
            self, user_prompt: str, system_prompt: str = ""
        ) -> dict[str, Any]:
            """Calls the OpenAI API and returns the API response."""
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            client = AsyncAnthropic(api_key=api_key)

            response = await client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=1000,
                temperature=0.0,
                system=system_prompt,
                messages=[
                    #     {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return response.model_dump()

        @staticmethod
        def parse_response(raw_response: dict[str, Any]) -> str:
            """Parses the API response and returns the response text."""
            response = raw_response["content"][0]["text"]
            pattern = r"^```json(?:\\n|\n)(.+?)(?:\\n|\n)```$"
            match = re.match(pattern, response, re.DOTALL)
            if match:
                return match.group(1)
            else:
                return response

    LLM.__name__ = model_class_name

    return LLM


if __name__ == "__main__":
    pass
    # ClaudeOpus = create_anthropic_model("claude-3-opus-20240229", "ClaudeOpus")
    # results = m.execute_model_call("How are you today?")
    # cleaned_up = ClaudeOpus.parse_response(results)
    # print(cleaned_up)
