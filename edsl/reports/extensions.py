from typing import Optional


from edsl import Scenario, ScenarioList, Dataset
from edsl import QuestionDict
from edsl import Scenario


class ScenarioListMixin:
    """Mixin class that adds semantic column functionality to ScenarioList."""

    def semantic_columns(self) -> "ScenarioList":
        if self.codebook is None:
            raise ValueError("codebook is not set")
        renaming_columns = self.better_columns()
        return self.rename(renaming_columns)

    def better_columns(self) -> dict:
        s = Scenario({"columns": self.codebook})
        q = QuestionDict(
            question_name="better_columns",
            question_text=(
                "These are the columns of a CSV file representing a survey: '{{ scenario.columns }}'. "
                "I could like to create, for each column, a better identifier that captures what that column means. "
                "<example>"
                """E.g., a column 'How was your experience at dinner' ---> 'dinner_experience'"""
                "</example> "
                "Please do thise for each column, but making sure each name is unique, with no duplicates. "
                "Please keep each one short, ideally one or two words. "
                "If the column name is unformative, repeat the identifier e.g., "
                "<example>"
                """{'col_5': 'Unamed'} ---> {'col_5': 'col_5'}"""
                "</example>"
            ),
            answer_keys=list(self.codebook.keys()),
        )
        new_columns = q.by(s).run(verbose=False)
        return new_columns.select("answer.*").first()


def extend_scenario_list():
    """Extend ScenarioList with semantic column functionality.

    This function adds the semantic_columns() and better_columns() methods to the ScenarioList class.
    It must be called before using these methods.

    Example:
        from edsl import ScenarioList
        from reports.extensions import extend_scenario_list

        # Extend ScenarioList with new functionality
        extend_scenario_list()

        # Now you can use semantic_columns()
        scenario_list = ScenarioList(...)
        result = scenario_list.semantic_columns()
    """
    # Add methods from mixin to ScenarioList
    for name, method in ScenarioListMixin.__dict__.items():
        if not name.startswith("__"):
            setattr(ScenarioList, name, method)


# Don't automatically extend - let users explicitly call extend_scenario_list()
# extend_scenario_list()


class DatasetNew(Dataset):
    def analyze(self, context: Optional[str] = None) -> "str":
        """
        Analyze the dataset and return results in appropriate format based on environment.

        Args:
            context: Optional additional context for the analysis

        Returns:
            str or IPython.display.Markdown: Markdown object in Jupyter environment, string otherwise
        """
        from edsl import QuestionFreeText

        data_in_json = self.to_pandas().to_json(orient="records", lines=True)
        q = QuestionFreeText(
            question_name="analysis",
            question_text=f"This is data from a study: {data_in_json}. {context}. Please write a short analysis of the data in markdown format.",
        )
        analysis = q.by(self).run(verbose=False).select("answer.*").first()

        # Check if we're in a Jupyter environment
        try:
            from IPython import get_ipython

            if get_ipython() is not None:
                from IPython.display import Markdown

                return Markdown(analysis)
        except ImportError:
            pass

        return analysis
