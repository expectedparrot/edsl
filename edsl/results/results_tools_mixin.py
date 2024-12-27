class ResultsToolsMixin:
    def get_themes(
        self,
        field: str,
        context: str,
        max_values=100,
        num_themes: int = 10,
        seed=None,
        progress_bar=False,
        print_exceptions=False,
    ) -> list:
        values = [
            str(txt)[:1000]
            for txt in self.shuffle(seed=seed).select(field).to_list()[:max_values]
        ]
        from edsl import ScenarioList
        from edsl.questions import QuestionList, QuestionCheckBox

        q = QuestionList(
            question_text=f"""
        {context}
        Here are some examples: { values }. 
        What are some 5-8 word themes that would mostly capture these examples?
        Please shoot for {num_themes} as target number of themes.
        """,
            question_name="themes",
        )
        results = q.run(print_exceptions=print_exceptions, progress_bar=progress_bar)
        return results.select("themes").first()

    def answers_to_themes(
        self,
        field,
        context: str,
        themes: list,
        progress_bar=False,
        print_exceptions=False,
    ) -> dict:
        from edsl import ScenarioList
        from edsl import QuestionCheckBox

        values = self.select(field).to_list()
        scenarios = ScenarioList.from_list("field", values).add_value(
            "context", context
        )
        q = QuestionCheckBox(
            question_text="""
            {{ context }}
            Consider the following response: 

            " {{ field }} "

            Please check the themes that apply to these examples.
            If blank, please check 'None'.
            """,
            question_options=themes + ["None", "Other"],
            question_name="themes",
        )
        results = q.by(scenarios).run(
            progress_bar=progress_bar, print_exceptions=print_exceptions
        )
        return {k: v for k, v in results.select("field", "themes").to_list()}

    def apply_themes(self, field: str, new_field: str, answers_to_themes: dict):
        def translate(x):
            return answers_to_themes.get(x, "Other")

        self.mutate(f"{new_field} = f({field})", functions_dict={"f": translate})
        return self

    def auto_theme(
        self,
        field: str,
        context: str,
        themes: list[str],
        newfield: str = None,
        progress_bar=False,
        print_exceptions=False,
    ) -> tuple:
        """
        :param field: The field to be themed.
        :param context: The context of the field.
        :param themes: The list of themes.
        :param newfield: The new field name.

        """

        if not newfield:
            newfield = f"{field}_themes"

        answers_to_themes = self.answers_to_themes(
            field=field,
            context=context,
            themes=themes,
            progress_bar=progress_bar,
            print_exceptions=print_exceptions,
        )
        return self.apply_themes(field, newfield, answers_to_themes), themes
