"""Composite application that pipes the output of one `App` into another.

This module defines `CompositeApp`, a lightweight wrapper that:
- runs a first `App`
- formats its output using an `ObjectFormatter` (the "pipe")
- passes the formatted data as params to a second `App`

It also supports simple dict-based serialization via `to_dict`/`from_dict`.
"""

from .app import App
from .output_formatter import ObjectFormatter


class CompositeApp:
    """Compose two `App` instances with an `ObjectFormatter` to form a pipeline.

    The first app is executed, its output is transformed by the provided
    formatter, and the transformed data is then provided as `params` to the
    second app.
    """

    # Align with App naming: expose an application_type for dispatch
    application_type: str = "composite"

    def __init__(self, first_app: App, pipe: ObjectFormatter, second_app:"CompositeApp"):
        """Initialize the composite pipeline.

        Args:
            first_app: The app executed first to produce initial output.
            second_app: The app executed after transformation; receives the
                transformed output as its `params`.
            pipe: The `ObjectFormatter` that transforms the first app's output
                into the parameters expected by the second app.
        """
        self.first_app = first_app
        self.second_app = second_app
        self.pipe = pipe

    def __rshift__(self, app: "App") -> "CompositeApp":
        self.second_app = app
        return self

    def output(self, params: dict):
        """Run the pipeline and return the second app's output.

        The `first_app` is executed with the provided `params`. Its output is
        then transformed by `pipe`, and the result is passed as `params` to
        `second_app`.

        Args:
            params: Parameters to pass into `first_app`.

        Returns:
            The return value of `second_app.output(...)`.
        """
        return self.second_app.output(
            params=self.first_app.with_output_formatter(self.pipe).output(params)
        )

    def to_dict(self):
        """Serialize this composite app to a dictionary.

        Returns:
            A dict with `application_type: "composite"` plus `first_app`,
            `second_app`, and `pipe` keys containing their respective
            serialized representations.
        """
        return {
            "application_type": self.application_type,
            "first_app": self.first_app.to_dict(),
            "second_app": self.second_app.to_dict(),
            "pipe": self.pipe.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Deserialize a `CompositeApp` from a dictionary.

        Args:
            data: Dictionary produced by `to_dict`.

        Returns:
            A `CompositeApp` instance reconstructed from the serialized data.
        """
        def _deserialize_app_or_composite(payload: dict):
            # Prefer explicit type dispatch when available
            if not isinstance(payload, dict):
                raise TypeError("Expected dict for app payload during deserialization")
            # New naming: application_type == "composite"
            if payload.get("application_type") == "composite":
                return cls.from_dict(payload)
            # Legacy compatibility: older tag
            if payload.get("composite_type") == "composite_app":
                return cls.from_dict(payload)
            if "application_type" in payload:
                return App.from_dict(payload)
            # Backward-compatibility: infer by presence of component keys
            if {"first_app", "second_app", "pipe"}.issubset(payload.keys()):
                return cls.from_dict(payload)
            # Fallback: treat as App
            return App.from_dict(payload)

        return cls(
            _deserialize_app_or_composite(data["first_app"]),
            _deserialize_app_or_composite(data["second_app"]),
            ObjectFormatter.from_dict(data["pipe"]),
        )


if __name__ == "__main__":
    from .app import SingleScenarioApp
    from .output_formatter import OutputFormatter

    from edsl import QuestionFreeText

    initial_survey = QuestionFreeText(
        question_name="input_text", question_text="What is the input text?"
    ).to_survey()

    jobs = QuestionFreeText(
        question_name="translated_text",
        question_text="Please translate {{ scenario.input_text }} to German. Just return the translated text, no other text.",
    ).to_jobs()

    of = (
        OutputFormatter(name="Output Formatter")
        .select("answer.*")
        .to_list()
        .__getitem__(0)
    )

    english_to_german = SingleScenarioApp(
        initial_survey=initial_survey,
        jobs_object=jobs,
        output_formatters=[of],
        application_name="to_german",
        description="Translate the input text to German.",
    )

    german_to_english = SingleScenarioApp(
        initial_survey=initial_survey,
        jobs_object=QuestionFreeText(
            question_name="translated_text",
            question_text="""Please translate {{ scenario.input_text }} from German to English. 
            Just return the translated text, no other text.""",
        ).to_jobs(),
        output_formatters=[of],
        application_name="to_german",
        description="Translate the input text from German to English.",
    )

    pipe = (
        OutputFormatter(name="Pipe")
        .select("answer.translated_text")
        .to_scenario_list()
        .rename({"translated_text": "input_text"})
        .__getitem__(0)
    )

    telephone_app = CompositeApp(english_to_german, german_to_english, pipe)
    results = telephone_app.output(
        params={
            "input_text": """Through some singular coincidence, I wouldn't be surprised if it were owing to the agency /
        of an ill natured fairy you are the victim of the clumsy arrangement having been born in leap year on/
         the 29th of February"""
        }
    )
    print(results)
