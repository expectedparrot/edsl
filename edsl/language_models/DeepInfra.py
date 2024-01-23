import aiohttp
import json
from typing import Any
from edsl import CONFIG
from edsl.enums import LanguageModelType, InferenceServiceType
from edsl.language_models.LanguageModel import LanguageModel


def create_deep_infra_model(model_name, url, model_class_name) -> LanguageModel:
    if not LanguageModelType.is_value_valid(model_name):
        acceptable_values = [item.value for item in LanguageModelType]
        raise Exception(
            f"""
        A Prompt's model must be one of {LanguageModelType} values, which are 
        currently {acceptable_values}. You passed {model_name}."""
        )

    class LLM(LanguageModel):
        _inference_service_ = InferenceServiceType.DEEP_INFRA.value
        _model_ = model_name
        _parameters_ = {
            "temperature": 0.5,
            "top_p": 1,
            "top_k": 1,
            "max_new_tokens": 2048,
            "stopSequences": [],
            "use_cache": True,
        }
        api_token = CONFIG.get("DEEP_INFRA_API_KEY")

        async def async_execute_model_call(
            self, user_prompt: str, system_prompt: str = ""
        ) -> dict[str, Any]:
            self.url = url
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Token {self.api_token}",
            }
            data = {
                "input": f"""
                [INST]<<SYS>> {system_prompt} 
                <<SYS>[/INST]
                {user_prompt} [/INST]
                """,
                "stream": False,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "top_k": self.top_k,
                "max_new_tokens": self.max_new_tokens,
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.url, headers=headers, data=json.dumps(data)
                ) as response:
                    raw_response_text = await response.text()
                    return json.loads(raw_response_text)

        def parse_response(self, raw_response: dict[str, Any]) -> str:
            return raw_response["results"][0]["generated_text"]

    LLM.__name__ = model_class_name

    return LLM


if __name__ == "__main__":
    pass
    # results = m.execute_model_call("Why is Cape Cod a popular vacation spot?")
    # print(m.parse_response(results))
