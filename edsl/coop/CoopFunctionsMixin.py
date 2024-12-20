class CoopFunctionsMixin:
    def better_names(self, existing_names):
        from edsl import QuestionList, Scenario

        s = Scenario({"existing_names": existing_names})
        q = QuestionList(
            question_text="""The following colum names are already in use: {{ existing_names }} 
                         Please provide new names for the columns.
                         They should be short, one or two words, and unique. They should be valid Python idenifiers. 
                         No spaces - use underscores instead. 
                         """,
            question_name="better_names",
        )
        results = q.by(s).run(verbose=False)
        return results.select("answer.better_names").first()
