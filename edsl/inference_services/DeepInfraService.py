import aiohttp
import json
import requests
from typing import Any
from edsl.inference_services.InferenceServiceABC import InferenceServiceABC
from edsl.language_models import LanguageModel


class DeepInfraService(InferenceServiceABC):
    """DeepInfra service class."""

    _inference_service_ = "deep_infra"
    _env_key_name_ = "DEEP_INFRA_API_KEY"

    @classmethod
    def available(cls):
        text_models = cls.full_details_available()
        return [m["model_name"] for m in text_models]

    @classmethod
    def full_details_available(cls, verbose=False):
        url = "https://api.deepinfra.com/models/list"
        response = requests.get(url)
        if response.status_code == 200:
            text_generation_models = [
                r for r in response.json() if r["type"] == "text-generation"
            ]
            from rich import print_json
            import json

            if verbose:
                print_json(json.dumps(text_generation_models))
            return text_generation_models
        else:
            return f"Failed to fetch data: Status code {response.status_code}"

    @classmethod
    def create_model(cls, model_name: str, model_class_name=None) -> LanguageModel:
        base_url = "https://api.deepinfra.com/v1/inference/"
        if model_class_name is None:
            model_class_name = cls.to_class_name(model_name)
        url = f"{base_url}{model_name}"

        class LLM(LanguageModel):
            _inference_service_ = cls._inference_service_
            _model_ = model_name
            _parameters_ = {
                "temperature": 0.7,
                "top_p": 0.2,
                "top_k": 0.1,
                "max_new_tokens": 512,
                "stopSequences": [],
            }

            async def async_execute_model_call(
                self, user_prompt: str, system_prompt: str = ""
            ) -> dict[str, Any]:
                self.url = url
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"bearer {self.api_token}",
                }
                # don't mess w/ the newlines
                data = {
                    "input": f"""
                    [INST]<<SYS>>
                    {system_prompt}
                    <<SYS>>{user_prompt}[/INST]
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
                if "results" not in raw_response:
                    raise Exception(
                        f"Deep Infra response does not contain 'results' key: {raw_response}"
                    )
                if "generated_text" not in raw_response["results"][0]:
                    raise Exception(
                        f"Deep Infra response does not contain 'generate_text' key: {raw_response['results'][0]}"
                    )
                return raw_response["results"][0]["generated_text"]

        LLM.__name__ = model_class_name

        return LLM
