from typing import List, Optional
from ..base import ItemCollection
from ..surveys import Survey

class SurveyList(ItemCollection):
    """A collection of Survey objects with methods for combining and analyzing surveys.
    
    This class extends ItemCollection to provide survey-specific functionality
    for managing multiple surveys and their questions.
    """

    item_class = Survey

    def combined_survey(self, keep: Optional[List[str]] = None, drop: Optional[List[str]] = None) -> 'Survey':
        """Combine all surveys into a single survey with optional filtering.
        
        Note: The resulting survey must have unique question names, so this method
        may not work if multiple surveys contain questions with the same name
        after filtering.
        
        Args:
            keep: List of question names to keep. If provided, only questions
                with these names will be included.
            drop: List of question names to drop. If provided, questions with
                these names will be excluded.
                
        Returns:
            A new Survey containing the combined questions from all surveys.
            
        Raises:
            ValueError: If both keep and drop parameters are specified, or if
                the resulting questions don't have unique names.
            
        Examples:
            >>> sl = SurveyList.example()
            >>> combined_keep = sl.combined_survey(keep=['name', 'color'])
            >>> len(combined_keep.questions)
            2
            >>> sorted([q.question_name for q in combined_keep.questions])
            ['color', 'name']
        """

        questions = []
        if keep is not None and drop is not None:
            raise ValueError("Cannot specify both keep and drop")
        if isinstance(keep, str):
            keep = [keep]
        if isinstance(drop, str):
            drop = [drop]

        for item in self:
            if keep is not None:
                questions.extend([q for q in item.questions if q.question_name in keep])
            elif drop is not None:
                questions.extend([q for q in item.questions if q.question_name not in drop])
            else:
                questions.extend(item.questions)

        return Survey(questions)
    
    @property
    def question_names_unique(self) -> bool:
        """Check if all question names across all surveys are unique.
        
        Returns:
            True if all question names are unique, False otherwise.
            
        Examples:
            >>> sl = SurveyList.example()
            >>> sl.question_names_unique
            True
            >>> from edsl import QuestionFreeText
            >>> q1 = QuestionFreeText(question_name="same", question_text="Question 1")
            >>> q2 = QuestionFreeText(question_name="same", question_text="Question 2")
            >>> s1 = Survey([q1])
            >>> s2 = Survey([q2])
            >>> duplicate_sl = SurveyList([s1, s2])
            >>> duplicate_sl.question_names_unique
            False
        """
        return len(set(self.question_names)) == len(self.question_names)
    
    @property
    def question_names(self) -> List[str]:
        """Get all question names from all surveys in the collection.
        
        Returns:
            List of question names from all surveys. May contain duplicates
            if the same question name appears in multiple surveys.
            
        Examples:
            >>> sl = SurveyList.example()
            >>> sorted(sl.question_names)
            ['age', 'color', 'food', 'name']
            >>> len(sl.question_names)
            4
        """
        question_names = []
        for survey in self:
            question_names.extend([q.question_name for q in survey.questions])
        return question_names
    
    @classmethod
    def example(cls) -> 'SurveyList':
        """Create an example SurveyList for testing and demonstration.
        
        Returns:
            A SurveyList containing two surveys with unique question names.
            The first survey has questions about name and age, and the second
            survey has questions about favorite color and food.
            
        Examples:
            >>> sl = SurveyList.example()
            >>> len(sl)
            2
            >>> len(sl[0].questions)
            2
            >>> len(sl[1].questions)
            2
        """
        from edsl import QuestionFreeText 
        q1 = QuestionFreeText(question_name = "name", question_text = "What is your name?")
        q2 = QuestionFreeText(question_name = "age", question_text = "What is your age?")
        q3 = QuestionFreeText(question_name = "color", question_text = "What is your favorite color?")
        q4 = QuestionFreeText(question_name = "food", question_text = "What is your favorite food?")
        survey1 = Survey([q1, q2], name="survey1")
        survey2 = Survey([q3, q4], name="survey2")
        return cls([survey1, survey2], name="Example SurveyList")
