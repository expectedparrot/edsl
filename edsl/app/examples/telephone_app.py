from __future__ import annotations

from edsl.app.composite_app import CompositeApp
from edsl.app.output_formatter import OutputFormatter
from edsl.app.app import App

from edsl import QuestionFreeText


def build_telephone_app() -> CompositeApp:
    initial_survey = QuestionFreeText(
        question_name="input_text", question_text="What is the input text?"
    ).to_survey()

    jobs_de = QuestionFreeText(
        question_name="translated_text",
        question_text="Please translate {{ scenario.input_text }} to German. Just return the translated text, no other text.",
    ).comment("Translating from English to German").to_jobs()

    of = (
        OutputFormatter(description="Output Formatter")
        .select("answer.*")
        .to_list()
        .__getitem__(0)
    )

    english_to_german = App(
        initial_survey=initial_survey,
        jobs_object=jobs_de,
        output_formatters={"of": of},
        default_formatter_name="of",
        application_name="to_german",
        description="Translate the input text to German.",
    )

    jobs_en = QuestionFreeText(
        question_name="translated_text",
        question_text="Please translate {{ scenario.input_text }} from German to English. Just return the translated text, no other text.",
    ).comment("Translating from German to English").to_jobs()

    german_to_english = App(
        initial_survey=initial_survey,
        jobs_object=jobs_en,
        output_formatters={"of": of},
        default_formatter_name="of",
        application_name="to_english",
        description="Translate the input text from German to English.",
    )

    bindings = {"of": "input_text"}

    return CompositeApp(
        first_app=english_to_german,
        second_app=german_to_english,
        bindings=bindings,
        fixed={"app1": {}, "app2": {}},
    )


if __name__ == "__main__":

    from edsl.app.app import App

    pirates_of_penzance_line = App(
        application_name="pirates_of_penzance_line",
        description="Returns a line from Pirates of Penzance.",
        initial_survey=QuestionFreeText(
            question_name="input_text",
            question_text="What character is speaking?",
        ).to_survey(),
        jobs_object=QuestionFreeText(
            question_name="example_line",
            question_text="Please return a line from Pirates of Penzance for the character {{ scenario.input_text }}.",
        ).comment("Getting line from Pirates of Penzance").to_jobs(),
        output_formatters={"of": OutputFormatter(description="Output Formatter").select("answer.*").to_list().__getitem__(0)},
        default_formatter_name="of")
        
    telephone_app = build_telephone_app()
    # results = telephone_app.output(
    #     params={
    #         "input_text": "Through some singular coincidence, I wouldn't be surprised if it were owing to the agency of an ill natured fairy you are the victim of the clumsy arrangement having been born in leap year on the 29th of February",
    #     }
    # )
    # print(results)

    nested_composite = CompositeApp(
        first_app=pirates_of_penzance_line,
        second_app=telephone_app,
        bindings={"of": "input_text"},
        fixed={"app1": {}, "app2": {}},
    )
    lazarus_app = CompositeApp.from_dict(nested_composite.to_dict())
    nested_results = lazarus_app.output(params={"input_text": "Mabel"})
    #nested_results = nested_composite.output(params={"input_text": "Mabel"})
    print(nested_results)


