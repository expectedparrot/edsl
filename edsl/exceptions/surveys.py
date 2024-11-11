from edsl.exceptions.BaseException import BaseException


class SurveyError(BaseException):
    relevant_doc = "https://docs.expectedparrot.com/en/latest/surveys.html"


class SurveyCreationError(SurveyError):
    pass


class SurveyHasNoRulesError(SurveyError):
    pass


class SurveyRuleSendsYouBackwardsError(SurveyError):
    pass


class SurveyRuleSkipLogicSyntaxError(SurveyError):
    pass


class SurveyRuleReferenceInRuleToUnknownQuestionError(SurveyError):
    pass


class SurveyRuleRefersToFutureStateError(SurveyError):
    pass


class SurveyRuleCollectionHasNoRulesAtNodeError(SurveyError):
    pass


class SurveyRuleCannotEvaluateError(SurveyError):
    pass
