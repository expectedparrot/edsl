from edsl import QuestionNumerical 
from edsl.inference_services.services import GoogleService
model = GoogleService().create_model("gemini-1.5-flash")()
model._api_token = 'fake'

if False:
    import asyncio

    async def main():
        result = await model.async_execute_model_call(
            user_prompt = "What is the population of Falmouth, MA in 2024?",
            system_prompt = "You are a helpful assistant that can answer questions about the population of Falmouth, MA in 2024.",
        )
        return result

    output = asyncio.run(main())
    print("Result:", output)


q = QuestionNumerical(
    question_name = "population", 
    question_text = "What is the population of Falmouth, MA in 2024?",
)
results = q.by(model).run(disable_remote_inference=True, 
                          cache = False,
                          fresh = True)
print(results)
