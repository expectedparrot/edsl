class ResultsToolsMixin:
    def get_themes(
        self, field, context: str, max_values=100, num_themes: int = 10, seed=None
    ) -> list:
        values = self.shuffle(seed=seed).select(field).to_list()
        if len(values) > max_values:
            print(
                f"Warning: too many values ({len(values)}). Truncating to {max_values}."
            )
            import random

            values = random.sample(values, max_values)
        from edsl.questions import QuestionList
        from edsl import ScenarioList

        q = QuestionList(
            question_text=f"""
        {context}
        Here are some examples: { values }. 
        What are some 5-8 word themes that would mostly capture these examples?
        Please shoot for {num_themes} as target number of themes.
        """,
            question_name="themes",
        )
        s = ScenarioList.from_list(field, values)
        results = q.by(s).run()
        return results.select("themes").first()

    def answers_to_themes(
        self, field, context: str, themes: list, progress_bar=False
    ) -> dict:
        from edsl import QuestionCheckBox, ScenarioList

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
        results = q.by(scenarios).run(progress_bar=progress_bar)
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
        num_themes: int = 10,
        seed=None,
        progress_bar=False,
    ):
        themes = self.get_themes(field, context, num_themes=num_themes, seed=seed)
        answers_to_themes = self.answers_to_themes(
            field, context, themes, progress_bar=progress_bar
        )
        return self.apply_themes(field, f"{field}_themes", answers_to_themes)
