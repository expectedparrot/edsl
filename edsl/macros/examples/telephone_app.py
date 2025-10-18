from __future__ import annotations

from edsl.macros.composite_macro import CompositeMacro
from edsl.macros.output_formatter import OutputFormatter
from edsl.macros.macro import Macro

from edsl import QuestionFreeText


def build_telephone_macro() -> CompositeMacro:
    initial_survey = QuestionFreeText(
        question_name="input_text", question_text="What is the input text?"
    ).to_survey()

    jobs_de = (
        QuestionFreeText(
            question_name="translated_text",
            question_text="Please translate {{ scenario.input_text }} to German. Just return the translated text, no other text.",
        )
        .comment("Translating from English to German")
        .to_jobs()
    )

    of = (
        OutputFormatter(description="Output Formatter")
        .select("answer.*")
        .to_list()
        .__getitem__(0)
    )

    english_to_german = Macro(
        application_name="to_german",
        display_name="English to German Translator",
        short_description="Translate the input text to German.",
        long_description="This application translates English text to German.",
        initial_survey=initial_survey,
        jobs_object=jobs_de,
        output_formatters={"of": of},
        default_formatter_name="of",
    )

    jobs_en = (
        QuestionFreeText(
            question_name="translated_text",
            question_text="Please translate {{ scenario.input_text }} from German to English. Just return the translated text, no other text.",
        )
        .comment("Translating from German to English")
        .to_jobs()
    )

    german_to_english = Macro(
        application_name="to_english",
        display_name="German to English Translator",
        short_description="Translate the input text from German to English.",
        long_description="This application translates German text to English.",
        initial_survey=initial_survey,
        jobs_object=jobs_en,
        output_formatters={"of": of},
        default_formatter_name="of",
    )

    bindings = {"of": "input_text"}

    return CompositeMacro(
        first_macro=english_to_german,
        second_macro=german_to_english,
        bindings=bindings,
        fixed={"macro1": {}, "macro2": {}},
    )


macro = build_telephone_macro()


if __name__ == "__main__":
    pirates_of_penzance_line = Macro(
        application_name="pirates_of_penzance_line",
        display_name="Pirates of Penzance Line Generator",
        short_description="Returns a line from Pirates of Penzance.",
        long_description="This application returns a line from the Gilbert and Sullivan operetta Pirates of Penzance for a specified character.",
        initial_survey=QuestionFreeText(
            question_name="input_text",
            question_text="What character is speaking?",
        ).to_survey(),
        jobs_object=QuestionFreeText(
            question_name="example_line",
            question_text="Please return a line from Pirates of Penzance for the character {{ scenario.input_text }}.",
        )
        .comment("Getting line from Pirates of Penzance")
        .to_jobs(),
        output_formatters={
            "of": OutputFormatter(description="Output Formatter")
            .select("answer.*")
            .to_list()
            .__getitem__(0)
        },
        default_formatter_name="of",
    )

    telephone_macro = build_telephone_macro()
    # results = telephone_macro.output(
    #     params={
    #         "input_text": "Through some singular coincidence, I wouldn't be surprised if it were owing to the agency of an ill natured fairy you are the victim of the clumsy arrangement having been born in leap year on the 29th of February",
    #     }
    # )
    # print(results)

    nested_composite = CompositeMacro(
        first_macro=pirates_of_penzance_line,
        second_macro=telephone_macro,
        bindings={"of": "input_text"},
        fixed={"macro1": {}, "macro2": {}},
    )

    # FIXME: CompositeMacro bindings currently have issues with MacroRunOutput serialization
    # When a formatter returns a MacroRunOutput and it's bound to the next macro's params,
    # the system tries to serialize it to JSON which fails.
    # This needs to be fixed in the CompositeMacro binding logic to automatically unwrap MacroRunOutput.
    print("Testing nested composite macro...")
    print(
        "WARNING: This test is currently disabled due to MacroRunOutput serialization issues."
    )
    print(
        "The CompositeMacro binding system needs to be updated to unwrap MacroRunOutput objects."
    )

    # try:
    #     nested_results = nested_composite.output(params={"input_text": "Mabel"})
    #     # MacroRunOutput cannot be JSON serialized directly - access the underlying data
    #     print("Result type:", type(nested_results))
    #     print(nested_results)
    # except Exception as e:
    #     print(f"Error running nested composite: {e}")

    # # Test serialization without trying to JSON serialize the result
    # nested_dict = nested_composite.to_dict()
    # lazarus_macro = CompositeMacro.from_dict(nested_dict)
    # nested_results = lazarus_macro.output(params={"input_text": "Mabel"})
    # # Don't try to JSON serialize MacroRunOutput - just print it
    # print(nested_results)
