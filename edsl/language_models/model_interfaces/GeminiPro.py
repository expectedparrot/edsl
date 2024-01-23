import aiohttp
import json
from typing import Any
from edsl import CONFIG
from edsl.language_models.LanguageModel import LanguageModel
from edsl.enums import LanguageModelType, InferenceServiceType


class GeminiPro(LanguageModel):
    _inference_service_ = InferenceServiceType.GOOGLE.value
    _model_ = LanguageModelType.GEMINI_PRO.value
    _parameters_ = {
        "temperature": 0.5,
        "topP": 1,
        "topK": 1,
        "maxOutputTokens": 2048,
        "stopSequences": [],
        "use_cache": True,
    }
    api_token = CONFIG.get("GOOGLE_API_KEY")

    async def async_execute_model_call(
        self, user_prompt: str, system_prompt: str = ""
    ) -> dict[str, Any]:
        combined_prompt = user_prompt + system_prompt
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={self.api_token}"
        headers = {"Content-Type": "application/json"}
        data = {
            "contents": [{"parts": [{"text": combined_prompt}]}],
            "generationConfig": {
                "temperature": self.temperature,
                "topK": self.topK,
                "topP": self.topP,
                "maxOutputTokens": self.maxOutputTokens,
                "stopSequences": self.stopSequences,
            },
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, headers=headers, data=json.dumps(data)
            ) as response:
                raw_response_text = await response.text()
                return json.loads(raw_response_text)

    def parse_response(self, raw_response: dict[str, Any]) -> str:
        data = raw_response
        return data["candidates"][0]["content"]["parts"][0]["text"]


if __name__ == "__main__":
    m = GeminiPro(use_cache=True)
    from edsl.questions import QuestionMultipleChoice

    q = QuestionMultipleChoice(
        question_text="Are pickled pigs feet a popular breakfast food in the US?",
        question_options=["Yes", "No", "Unsure"],
        question_name="bkfast_question",
    )
    results = q.by(m).run()
    from rich import print

    print(q)
    results.select("answer.*", "model.model").print()
    # results = m.execute_model_call("Why is Cape Cod a popular vacation spot?")
    # print(m.parse_response(results))
