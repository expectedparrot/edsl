from edsl.exceptions.BaseException import BaseException


class SurveyErrors(BaseException):
    relevant_doc = "https://docs.expectedparrot.com/en/latest/surveys.html"


class SurveyCreationError(SurveyErrors):
    pass


class SurveyHasNoRulesError(SurveyErrors):
    pass


class SurveyRuleSendsYouBackwardsError(SurveyErrors):
    pass


class SurveyRuleSkipLogicSyntaxError(SurveyErrors):
    pass


class SurveyRuleReferenceInRuleToUnknownQuestionError(SurveyErrors):
    pass


class SurveyRuleRefersToFutureStateError(SurveyErrors):
    pass


class SurveyRuleCollectionHasNoRulesAtNodeError(SurveyErrors):
    pass


class SurveyRuleCannotEvaluateError(SurveyErrors):
    pass
