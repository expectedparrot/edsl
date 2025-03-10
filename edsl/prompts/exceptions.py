from ..base import BaseException

class PromptError(BaseException):
    pass


class TemplateRenderError(PromptError):
    "TODO: Move to exceptions file"
    pass


class PromptBadQuestionTypeError(PromptError):
    pass


class PromptBadLanguageModelTypeError(PromptError):
    pass
