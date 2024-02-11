import aiohttp
import json
import types
from typing import Any
from edsl import CONFIG
from edsl.enums import LanguageModelType, InferenceServiceType
from edsl.language_models.LanguageModel import LanguageModel

def parrotify(language_model):
    """This takes an existing language model and adds the ExpectedParrot async_execute_model_call method to it."""
    async def async_execute_model_call(self, user_prompt: str, system_prompt: str = "") -> dict[str, Any]:
        #self.url = f"{CONFIG.get('EDSL_API_URL')}/execute_model"
        url = "http://127.0.0.1:8000" + "/execute_model"
        api_token = CONFIG.get("EMERITUS_API_KEY")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Token {api_token}",
        }

        data = {
            "system_prompt": system_prompt, 
            "user_prompt": user_prompt,
            "temperature": getattr(self, "temperature", 0.5),
            "top_p": getattr(self, "top_p", 1),
            "top_k": getattr(self, "top_k", 1),
            "model": self.model,
            "max_new_tokens": getattr(self, "max_new_tokens"), 
            # "inference_service": self._inference_service_,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, headers=headers, data=json.dumps(data)
            ) as response:
                raw_response_text = await response.text()
                return json.loads(raw_response_text)
    
    # replaces the async_execute_model_call method with the new one
    setattr(language_model, "async_execute_model_call", types.MethodType(async_execute_model_call, language_model))
    return language_model
    
if __name__ == "__main__":
    from edsl import Model
    m1 = parrotify(Model(LanguageModelType.MIXTRAL_8x7B_INSTRUCT.value, use_cache=False))
    m2 = parrotify(Model(LanguageModelType.GEMINI_PRO.value, use_cache=False))
    m3 = parrotify(Model(LanguageModelType.GPT_4.value, use_cache=False))
    from edsl.questions import QuestionFreeText
    q = QuestionFreeText(question_name = "how_are_you", question_text = "What is the meaning of life?")
    results = q.by(m1, m2, m3).run()
    results.print_long()


