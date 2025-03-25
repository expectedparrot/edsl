from __future__ import annotations
from typing import Optional
from .question_multiple_choice import QuestionMultipleChoice
from .decorators import inject_exception


class QuestionLikertFive(QuestionMultipleChoice):
    """
    A specialized question that prompts the agent to respond on a 5-point Likert scale.
    
    QuestionLikertFive is a subclass of QuestionMultipleChoice that presents a standard
    5-point Likert scale ranging from "Strongly disagree" to "Strongly agree". This
    question type is ideal for measuring attitudes, opinions, and perceptions on a
    symmetric agree-disagree scale.
    
    Key Features:
    - Pre-configured with standard Likert scale options
    - Simplifies creating consistent Likert scale questions
    - Inherits all functionality from QuestionMultipleChoice
    - Can be customized with different options if needed
    
    Technical Details:
    - Uses the standard Likert options: ["Strongly disagree", "Disagree", "Neutral", "Agree", "Strongly agree"]
    - Implements `use_code=False` by default, so responses contain the text labels
    - Can be connected to language models and agents like any other question
    
    Examples:
        Basic usage:
        
        ```python
        q = QuestionLikertFive(
            question_name="climate_concern",
            question_text="I am concerned about climate change."
        )
        ```
        
        With custom options:
        
        ```python
        q = QuestionLikertFive(
            question_name="satisfaction",
            question_text="I am satisfied with the product.",
            question_options=["Strongly Disagree", "Somewhat Disagree", 
                              "Neither Agree nor Disagree", 
                              "Somewhat Agree", "Strongly Agree"]
        )
        ```
        
    Notes:
        - Likert scales are particularly useful for surveys and opinion research
        - The default options follow the most common 5-point Likert scale format
        - For different scales (e.g., 7-point), you can pass custom options
    """

    question_type = "likert_five"
    likert_options: list[str] = [
        "Strongly disagree",
        "Disagree",
        "Neutral",
        "Agree",
        "Strongly agree",
    ]

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: Optional[list[str]] = None,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
        include_comment: bool = True,
    ):
        """
        Initialize a new 5-point Likert scale question.
        
        Parameters
        ----------
        question_name : str
            The name of the question, used as an identifier. Must be a valid Python variable name.
            This name will be used in results, templates, and when referencing the question in surveys.
            
        question_text : str
            The statement to which the agent will respond on the Likert scale. This is typically
            phrased as a statement rather than a question, e.g., "I enjoy using this product."
            
        question_options : Optional[list[str]], default=None
            Optional custom Likert scale options. If None, the default 5-point Likert scale options
            are used: ["Strongly disagree", "Disagree", "Neutral", "Agree", "Strongly agree"].
            Custom options should follow the same format (typically 5 or 7 points from negative to positive).
            
        answering_instructions : Optional[str], default=None
            Custom instructions for how the model should answer the question. If None,
            default instructions for Likert scale questions will be used.
            
        question_presentation : Optional[str], default=None
            Custom template for how the question is presented to the model. If None,
            the default presentation for Likert scale questions will be used.
            
        include_comment : bool, default=True
            Whether to include a comment field in the response, allowing the model to provide
            additional explanation beyond just selecting an option on the scale.
            
        Examples
        --------
        >>> q = QuestionLikertFive(
        ...     question_name="product_satisfaction",
        ...     question_text="I am satisfied with the product."
        ... )
        
        >>> q_custom = QuestionLikertFive(
        ...     question_name="service_quality",
        ...     question_text="The service quality was excellent.",
        ...     question_options=["Completely Disagree", "Somewhat Disagree", 
        ...                      "Neutral", "Somewhat Agree", "Completely Agree"]
        ... )
        
        Notes
        -----
        - The default Likert options can be accessed via QuestionLikertFive.likert_options
        - Likert scale questions inherently use text labels rather than numeric codes
        - The statement should be phrased such that agreeing or disagreeing makes sense
        """
        # Use default Likert options if none are provided
        if question_options is None:
            question_options = self.likert_options
        super().__init__(
            question_name=question_name,
            question_text=question_text,
            question_options=question_options,
            use_code=False,
            include_comment=include_comment,
            answering_instructions=answering_instructions,
            question_presentation=question_presentation,
        )

    @classmethod
    @inject_exception
    def example(cls) -> QuestionLikertFive:
        """Return an example question."""
        return cls(
            question_name="happy_raining",
            question_text="I'm only happy when it rains.",
        )


def main():
    """Test QuestionLikertFive."""
    # Use the class directly since we're already in the module
    q = QuestionLikertFive.example()
    q.question_text
    q.question_options
    q.question_name
    # validate an answer
    q._validate_answer({"answer": 0, "comment": "I like custard"})
    # translate answer code
    q._translate_answer_code_to_answer(0, {})
    q._simulate_answer()
    q._simulate_answer(human_readable=False)
    q._validate_answer(q._simulate_answer(human_readable=False))
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q

    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
