import asyncio
import aiohttp
import json
from typing import Any

from edsl import CONFIG

from edsl.language_models.LanguageModel import LanguageModel


def replicate_model_factory(model_name, base_url, api_token):
    class ReplicateLanguageModelBase(LanguageModel):
        _model_ = (
            model_name  # Example model name, replace with actual model name if needed
        )
        _parameters_ = {
            "temperature": 0.1,
            "topK": 50,
            "topP": 0.9,
            "max_new_tokens": 500,
            "min_new_tokens": -1,
            "repetition_penalty": 1.15,
            #       "version": "5fe0a3d7ac2852264a25279d1dfb798acbc4d49711d126646594e212cb821749",
            "use_cache": True,
        }
        _api_token = api_token
        _base_url = base_url

        async def async_execute_model_call(
            self, user_prompt: str, system_prompt: str = ""
        ) -> dict[str, Any]:
            self.api_token = self._api_token
            self.headers = {
                "Authorization": f"Token {self.api_token}",
                "Content-Type": "application/json",
            }
            # combined_prompt = f"{system_prompt} {user_prompt}".strip()
            # print(f"Prompt: {combined_prompt}")
            data = {
                #          "version": self._parameters_["version"],
                "input": {
                    "debug": False,
                    "top_k": self._parameters_["topK"],
                    "top_p": self._parameters_["topP"],
                    "prompt": user_prompt,
                    "system_prompt": system_prompt,
                    "temperature": self._parameters_["temperature"],
                    "max_new_tokens": self._parameters_["max_new_tokens"],
                    "min_new_tokens": self._parameters_["min_new_tokens"],
                    "prompt_template": "{prompt}",
                    "repetition_penalty": self._parameters_["repetition_penalty"],
                },
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._base_url, headers=self.headers, data=json.dumps(data)
                ) as response:
                    raw_response_text = await response.text()
                    data = json.loads(raw_response_text)
                    print(f"This was the data returned by the model:{data}")
                    prediction_url = data["urls"]["get"]

                while True:
                    async with session.get(
                        prediction_url, headers=self.headers
                    ) as get_response:
                        if get_response.status != 200:
                            # Handle non-success status codes appropriately
                            return None

                        get_data = await get_response.text()
                        get_data = json.loads(get_data)
                        if get_data["status"] == "succeeded":
                            return get_data
                        await asyncio.sleep(1)

        def parse_response(self, raw_response: dict[str, Any]) -> str:
            data = "".join(raw_response["output"])
            print(f"This is what the model returned: {data}")
            return data

    return ReplicateLanguageModelBase
