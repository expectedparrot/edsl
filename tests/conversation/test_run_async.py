"""Minimal test of run_async with Google model"""

import asyncio
from edsl import QuestionFreeText, Model, Agent, Scenario


async def test_run_async():
    print("\n=== Starting run_async test ===")

    # Create a simple question
    q = QuestionFreeText(question_text="Say hello", question_name="greeting")
    m = Model("gemini-2.0-flash", service_name="google")
    a = Agent(name="TestAgent", traits={"role": "friendly"})
    s = Scenario({"context": "test"})
    jobs = q.by(s).by(a).by(m)
    results = await jobs.run_async(disable_remote_inference=False)
    return results


if __name__ == "__main__":
    results = asyncio.run(test_run_async())
    print("\n=== Test completed successfully ===")
    results.select("answer.*")
