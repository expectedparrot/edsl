import asyncio
import openai
import re
from typing import Any
from edsl import CONFIG
from edsl.language_models import LanguageModel

openai.api_key = CONFIG.get("OPENAI_API_KEY")

from openai import AsyncOpenAI

client = AsyncOpenAI()


class LanguageModelOpenAIFour(LanguageModel):
    """
    Child class of LanguageModel for interacting with OpenAI GPT-4 model.
    """

    _model_ = "gpt-4-1106-preview"
    # _model_ = "gpt-4"
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

    async def async_execute_model_call(
        self, prompt: str, system_prompt: str = ""
    ) -> dict[str, Any]:
        """Calls the OpenAI API and returns the API response."""
        response = await client.chat.completions.create(
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
        )
        return response.model_dump()

    # def execute_model_call(
    #     self, prompt: str, system_prompt: str = ""
    # ) -> dict[str, Any]:
    #     return asyncio.run(
    #         self._execute_model_call(prompt=prompt, system_prompt=system_prompt)
    #     )

    @staticmethod
    def parse_response(raw_response: dict[str, Any]) -> str:
        """Parses the API response and returns the response text."""
        response = raw_response["choices"][0]["message"]["content"]
        pattern = r"^```json(?:\\n|\n)(.+?)(?:\\n|\n)```$"
        match = re.match(pattern, response, re.DOTALL)
        if match:
            return match.group(1)
        else:
            return response


if __name__ == "__main__":
    from edsl.language_models import LanguageModelOpenAIFour
    import threading

    m = LanguageModelOpenAIFour(use_cache=False, temperature=1)

    class TaskResults:
        def __init__(self, total_tasks):
            self.data = []
            self.lock = threading.Lock()
            self.total_tasks = total_tasks

        def add_result(self, result):
            with self.lock:
                self.data.append(result)

        @property
        def is_complete(self):
            return len(self.data) == self.total_tasks

        @property
        def status(self):
            pct_complete = round(100 * len(self.data) / self.total_tasks, 0)
            return f"Percent completed: {pct_complete}%"

    num_tasks = 100
    results = TaskResults(num_tasks)

    async def task(results_object, index):
        result = await m.get_response(
            system_prompt="""
            You are a helpful AI agent. Only respond briefly, without asking any questions.
            Response with valid JSON of the form: {"response": "your response here"}
            """,
            prompt=f"""Take this number, {index} and add 100 to it.""",
        )
        results_object.add_result(result)
        return result

    async def main_async(results_object):
        tasks = [task(results_object, index) for index in range(num_tasks)]
        full_results = await asyncio.gather(*tasks)
        return full_results

    def run_async_code_in_thread(results_obj):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main_async(results_obj))
        loop.close()

    t = threading.Thread(target=run_async_code_in_thread, args=(results,))
    t.start()
    # import time

    # start_time = time.time()
    # full_results = asyncio.run(main())
    # end_time = time.time()
    # print(f"Elapsed time: {end_time - start_time}")

    # m.execute_model_call(
    #     system_prompt="Pretend you are human. Do not break character. Only respond shortly, without asking any questions.",
    #     prompt="How are you?",
    # )
    # raw_english = m.get_raw_response(
    #     system_prompt="Pretend you are human. Do not break character. Only respond shortly, without asking any questions.",
    #     prompt="What is your favorite color?",
    # )
    # print(m.parse_response(raw_english))
    # print(m.cost(raw_english))

    # # ----
    # system_prompt = "Pretend you are human. Do not break character. Only respond shortly, without asking any questions."
    # prompt = "What is your favorite color?"
    # m = LanguageModelOpenAIFour(use_cache=True)
    # # the execute model call should be a dict
    # raw_german = m.execute_model_call(system_prompt=system_prompt, prompt=prompt)
    # raw_german = m.get_raw_response(system_prompt=system_prompt, prompt=prompt)
    # print(raw_german)
    # print(m.parse_response(raw_german))
    # print(m.cost(raw_german))
