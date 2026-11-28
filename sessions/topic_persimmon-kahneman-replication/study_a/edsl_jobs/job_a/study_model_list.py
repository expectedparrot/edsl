from pathlib import Path
from edsl import Model, ModelList

# Direct local inference is required for Persimmon because its service is not
# hosted by Expected Parrot. The same local path is used for the OpenAI arm.
model_list = ModelList(
    [
        Model(
            "persimmon-v0.1",
            service_name="persimmon",
            max_tokens=128,
        ),
        Model(
            "gpt-6.2-sol",
            service_name="openai",
            max_tokens=128,
        ),
    ]
)

if __name__ == "__main__":
    model_list.git.save(str(Path(__file__).with_name("model_list.ep")))
