class PromptError(Exception):
    pass


class TemplateRenderError(PromptError):
    "TODO: Move to exceptions file"
    pass


class PromptBadQuestionTypeError(PromptError):
    pass


class PromptBadLanguageModelTypeError(PromptError):
    pass
