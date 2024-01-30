import copy
from collections import UserDict
from rich.table import Table

from edsl.Base import Base


class Scenario(Base, UserDict):
    """A Scenario is a dictionary of key/values that describe some situation."""

    def __add__(self, other_scenario):
        """Combine two scenarios. If the other scenario is None, then just return self.
        >>> s1 = Scenario({"price": 100, "quantity": 2})
        >>> s2 = Scenario({"color": "red"})
        >>> s1 + s2
        {'price': 100, 'quantity': 2, 'color': 'red'}
        >>> (s1 + s2).__class__.__name__
        'Scenario'
        """
        if other_scenario is None:
            return self
        else:
            new_scenario = Scenario()
            new_scenario.data = copy.deepcopy(self.data)
            new_scenario.update(copy.deepcopy(other_scenario))
            return Scenario(new_scenario)

    def to(self, question_or_survey) -> "Jobs":
        """Run a question/survey with this particular scenario.
        Useful if you want to reverse the typical chain of operations.

        >>> from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice
        >>> s = Scenario({"food": "wood chips"})
        >>> q = QuestionMultipleChoice(question_text = "Do you enjoy the taste of {{food}}?", question_options = ["Yes", "No"], question_name = "food_preference")
        >>> _ = s.to(q)
        """
        return question_or_survey.by(self)

    def rename(self, replacement_dict: dict) -> "Scenario":
        """Rename the keys of a scenario. Useful for changing the names of keys.

        >>> s = Scenario({"food": "wood chips"})
        >>> s.rename({"food": "food_preference"})
        {'food_preference': 'wood chips'}
        """
        new_scenario = Scenario()
        for key, value in self.items():
            if key in replacement_dict:
                new_scenario[replacement_dict[key]] = value
            else:
                new_scenario[key] = value
        return new_scenario

    def make_question(self, question_class: type):
        """Make a question from this scenario. Note it takes a QuestionClass (not a question)
        as an input.

        >>> from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice
        >>> from edsl.agents.Agent import Agent

        >>> s = Scenario({"question_name": "feelings",
        ...               "question_text": "How are you feeling?",
        ...               "question_options": ["Very sad.", "Sad.", "Neutral.", "Happy.", "Very happy."]})
        >>> q = s.make_question(QuestionMultipleChoice)
        >>> q.by(Agent(traits = {'feeling': 'Very sad'})).run().select("feelings")
        [{'answer.feelings': ['Very sad.']}]
        """
        return question_class(**self)

    def to_dict(self):
        """Convert a scenario to a dictionary.
        >>> s = Scenario({"food": "wood chips"})
        >>> s.to_dict()
        {'food': 'wood chips'}
        """
        return self.data

    @classmethod
    def from_dict(cls, d):
        """Convert a dictionary to a scenario.
        >>> Scenario.from_dict({"food": "wood chips"})
        {'food': 'wood chips'}
        """
        return cls(d)

    def _table(self) -> tuple[dict, list]:
        """Prepare generic table data."""
        table_data = []
        for attr_name, attr_value in self.__dict__.items():
            table_data.append({"Attribute": attr_name, "Value": repr(attr_value)})
        column_names = ["Attribute", "Value"]
        return table_data, column_names

    def rich_print(self):
        """Displays an object as a rich table."""
        table_data, column_names = self._table()
        table = Table(title=f"{self.__class__.__name__} Attributes")
        for column in column_names:
            table.add_column(column, style="bold")

        for row in table_data:
            row_data = [row[column] for column in column_names]
            table.add_row(*row_data)

        return table

    @classmethod
    def example(cls):
        """Returns an example scenario.
        >>> Scenario.example()
        {'persona': 'A reseacher studying whether LLMs can be used to generate surveys.'}
        """
        return cls(
            {
                "persona": "A reseacher studying whether LLMs can be used to generate surveys."
            }
        )

    def code(self):
        """Returns the code for the scenario."""
        lines = []
        lines.append("from edsl.scenario import Scenario")
        return f"Scenario({self.data})"


if __name__ == "__main__":
    import doctest

    doctest.testmod()
