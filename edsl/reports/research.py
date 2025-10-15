from edsl import Results 
from .utilities import HTMLSnippet
from .charts import ChartOutput
from .tables import TableOutput

class Research:
    """Analysis on a question or set of questions from an edsl Results object."""

    def __init__(self, results: Results, question_names: list[str], *, allowed_output_names: list[str] | None = None, free_text_sample_config: dict[str, int] | None = None):
        self.results = results
        self.question_names = tuple(question_names)
        self.questions = [self.results.survey.get(name) for name in self.question_names]
        self._allowed_output_names = set(allowed_output_names) if allowed_output_names is not None else None
        self.free_text_sample_config = free_text_sample_config or {}
        self.relevant_outputs = self._relevant_outputs()
        self.generated_outputs = self._generate_outputs()

    @property
    def title(self) -> str:
        """The title of the research item."""
        return ", ".join(self.question_names)

    def __repr__(self) -> str:
        """Provides a developer-friendly representation of the Research object."""
        return f"Research(results=..., question_names={self.question_names})"

    def _relevant_outputs(self) -> dict[str, type['Output']]:
        relevant_outputs = {}
        for output_class in [ChartOutput, TableOutput]:
            available_outputs = output_class.get_available_outputs()
            for output_name, output_class in available_outputs.items():
                if output_class.can_handle(*self.questions):
                    if self._allowed_output_names is None or output_name in self._allowed_output_names:
                        relevant_outputs[output_name] = output_class
        return relevant_outputs
    
    def _generate_outputs(self) -> dict[str, type['Output']]:
        generated_outputs = {}
        for name, output_class in self.relevant_outputs.items():
            # Check if this output class supports free text sampling configuration
            if hasattr(output_class, '__init__') and 'free_text_sample_config' in output_class.__init__.__code__.co_varnames:
                generated_outputs[name] = output_class(self.results, *self.question_names, free_text_sample_config=self.free_text_sample_config)
            else:
                generated_outputs[name] = output_class(self.results, *self.question_names)
        return generated_outputs
    
    def html(self) -> str:
        """Generate a string of HTML for the research item."""
        html = ""
        for output_name, output in self.generated_outputs.items():
            html += f"<h2>{output_name}</h2>"
            html += output.html
        return HTMLSnippet(html)
    
    # ----------------------
    # Helper / utility APIs
    # ----------------------

    @staticmethod
    def get_possible_output_names(results: Results, question_names: list[str]) -> list[str]:
        """Return list of output names supported for the given question(s).

        This inspects all registered ChartOutput and TableOutput subclasses and
        applies their *can_handle* logic without instantiating a Research object.
        """
        questions = [results.survey.get(name) for name in question_names]
        possible = []
        for output_class in [ChartOutput, TableOutput]:
            available = output_class.get_available_outputs()
            for name, cls in available.items():
                try:
                    if cls.can_handle(*questions):
                        possible.append(name)
                except Exception:
                    # If can_handle raises, treat as False
                    continue
        return possible

if __name__ == "__main__":
    # Example using the new Report class

    # Load example results
    results = Results.example()

    r = Research(results, ["how_feeling"])
    r.html().view()
