from .app import App
from .output_formatter import ObjectFormatter


class CompositeApp:

    def __init__(self, first_app: App, second_app: App, pipe: ObjectFormatter):
        self.first_app = first_app
        self.second_app = second_app
        self.pipe = pipe

    def output(self, params: dict):
        return self.second_app.output(
            params=self.first_app.with_output_formatter(self.pipe).output(params)
        )

    def to_dict(self):
        return {
            "first_app": self.first_app.to_dict(),
            "second_app": self.second_app.to_dict(),
            "pipe": self.pipe.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            App.from_dict(data["first_app"]),
            App.from_dict(data["second_app"]),
            ObjectFormatter.from_dict(data["pipe"]),
        )


if __name__ == "__main__":
    from .app import SingleScenarioApp
    from .output_formatter import OutputFormatter, ScenarioAttachmentFormatter

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
