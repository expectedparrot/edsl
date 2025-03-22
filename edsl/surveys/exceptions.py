from ..base import BaseException

class SurveyError(BaseException):
    """
    Base exception class for all survey-related errors.
    
    This exception is the parent class for all exceptions related to Survey operations,
    including creation, validation, and navigation. It provides a common type
    for catching any survey-specific error.
    
    This exception is raised directly when:
    - Question names don't meet validation requirements
    - Survey operations encounter general errors not covered by more specific exceptions
    """
    doc_page = "surveys"


class SurveyCreationError(SurveyError):
    """
    Exception raised when there's an error creating or modifying a survey.
    
    This exception occurs when:
    - Adding skip rules to EndOfSurvey (which isn't allowed)
    - Combining surveys with non-default rules
    - Adding questions with duplicate names
    - Creating invalid question groups
    - Validating group names and boundaries
    
    To fix this error:
    1. Ensure all question names in a survey are unique
    2. Don't add skip rules to EndOfSurvey
    3. Check that question groups are properly defined
    4. When combining surveys, ensure they're compatible
    
    Examples:
        ```python
        survey.add(question)  # Raises SurveyCreationError if question's name already exists
        survey.add_rules_to_question(EndOfSurvey)  # Raises SurveyCreationError
        ```
    """
    doc_anchor = "creating-surveys"


class SurveyHasNoRulesError(SurveyError):
    """
    Exception raised when rules are required but not found for a question.
    
    This exception occurs when:
    - The survey's next_question method is called but no rules exist for the current question
    - Navigation can't proceed because there's no defined path forward
    
    To fix this error:
    1. Add appropriate rules to all questions in the survey
    2. Ensure the survey has a complete navigation path from start to finish
    3. Use default rules where appropriate (add_default_rules method)
    
    Examples:
        ```python
        survey.next_question(0)  # Raises SurveyHasNoRulesError if question 0 has no rules
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/surveys.html#rules"


class SurveyRuleSendsYouBackwardsError(SurveyError):
    """
    Exception raised when a rule would navigate backward in the survey flow.
    
    This exception occurs during rule initialization to prevent rules that
    would navigate backward in the survey flow, which is not allowed.
    
    Backward navigation creates potential loops and is generally considered
    poor survey design. EDSL enforces forward-only navigation.
    
    To fix this error:
    1. Redesign your survey to avoid backward navigation
    2. Use forward-only rules with proper branching logic
    3. Consider using memory to carry forward information if needed
    
    Examples:
        ```python
        survey.add_rule(question_index=2, rule=Rule(lambda x: True, 1))  # Raises SurveyRuleSendsYouBackwardsError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/surveys.html#rules"


class SurveyRuleSkipLogicSyntaxError(SurveyError):
    """
    Exception raised when a rule's expression has invalid syntax.
    
    This exception occurs when:
    - The expression in a rule is not valid Python syntax
    - The expression can't be parsed or compiled
    
    To fix this error:
    1. Check the syntax of your rule expression
    2. Ensure all variables in the expression are properly referenced
    3. Test the expression in isolation to verify it's valid Python
    
    Examples:
        ```python
        Rule(lambda x: x[question] ==, 1)  # Raises SurveyRuleSkipLogicSyntaxError (invalid syntax)
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/surveys.html#rules"


class SurveyRuleReferenceInRuleToUnknownQuestionError(SurveyError):
    """
    Exception raised when a rule references an unknown question.
    
    This exception is designed to catch cases where a rule's condition
    references a question that doesn't exist in the survey.
    
    To fix this error:
    1. Ensure all questions referenced in rule conditions exist in the survey
    2. Check for typos in question names or indices
    
    Note: This exception is defined but not actively used in the codebase.
    It raises Exception("not used") to indicate this state.
    """
    def __init__(self, message="Rule references an unknown question", **kwargs):
        super().__init__(message, **kwargs)


class SurveyRuleRefersToFutureStateError(SurveyError):
    """
    Exception raised when a rule references questions that come later in the survey.
    
    This exception occurs when:
    - A rule condition refers to questions that haven't been presented yet
    - Rule evaluation would require information not yet collected
    
    To fix this error:
    1. Redesign your rules to only reference current or previous questions
    2. Ensure rule conditions only depend on information already collected
    3. Restructure your survey if you need different branching logic
    
    Examples:
        ```python
        # If question 3 hasn't been asked yet:
        Rule(lambda x: x['q3_answer'] == 'Yes', next_question=4)  # Raises SurveyRuleRefersToFutureStateError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/surveys.html#rules"


class SurveyRuleCollectionHasNoRulesAtNodeError(SurveyError):
    """
    Exception raised when no rules are found for a specific question during navigation.
    
    This exception occurs when:
    - The RuleCollection's next_question method can't find applicable rules
    - A survey is trying to determine the next question but has no rule for the current state
    
    To fix this error:
    1. Add rules for all questions in your survey
    2. Ensure rules are properly added to the RuleCollection
    3. Add default rules where appropriate
    
    Examples:
        ```python
        # If rule_collection has no rules for question 2:
        rule_collection.next_question(2, {})  # Raises SurveyRuleCollectionHasNoRulesAtNodeError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/surveys.html#rule-collections"


class SurveyRuleCannotEvaluateError(SurveyError):
    """
    Exception raised when a rule expression cannot be evaluated.
    
    This exception occurs when:
    - The rule's expression fails to evaluate with the provided data
    - Required variables are missing in the evaluation context
    - The expression contains errors that only appear at runtime
    
    To fix this error:
    1. Check that your rule expression is valid
    2. Ensure all referenced variables are available in the context
    3. Add error handling in complex expressions
    4. Test rules with sample data before using in production
    
    Examples:
        ```python
        # If 'q1_answer' is not in the data dictionary:
        Rule(lambda x: x['q1_answer'] == 'Yes', 2).evaluate({})  # Raises SurveyRuleCannotEvaluateError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/surveys.html#rules"
