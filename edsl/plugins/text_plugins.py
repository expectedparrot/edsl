from ..extension_manager.plugin_system import PluginInterface

class TextProcessor(PluginInterface):
    """Plugin for processing text."""
    
    def uppercase(self, text: str) -> str:
        """Convert text to uppercase."""
        return text.upper()
    
    def lowercase(self, text: str) -> str:
        """Convert text to lowercase."""
        return text.lower()
    
    def reverse(self, text: str) -> str:
        """Reverse the text."""
        return text[::-1]
    
    def word_count(self, text: str) -> int:
        """Count the number of words in the text."""
        return len(text.split())
    
    def cognitive_testing(self, survey: "Survey") -> str:
        from edsl import QuestionFreeText, Scenario
        questions = "\n".join([q.question_text for q in survey.questions])
        q = QuestionFreeText(
            question_name="cognitive_testing",
            question_text = "What do you think of the following questions: {{ questions }}?"
        )
        results = q.by(Scenario({'questions':questions})).run(verbose = False)
        return results.select('answer.cognitive_testing').first()
        #survey.add_question(q)
        #return survey

