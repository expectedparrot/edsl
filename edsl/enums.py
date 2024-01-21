from enum import Enum


class EnumWithChecks(Enum):
    @classmethod
    def is_value_valid(cls, value):
        return any(value == item.value for item in cls)


class QuestionType(EnumWithChecks):
    MULTIPLE_CHOICE = "multiple_choice"
    YES_NO = "yes_no"
    FREE_TEXT = "free_text"
    RANK = "rank"
    BUDGET = "budget"
    CHECKBOX = "checkbox"
    EXTRACT = "extract"
    FUNCTIONAL = "functional"
    LIST = "list"
    NUMERICAL = "numerical"
    TOP_K = "top_k"
    LIKERT_FIVE = "likert_five"
    LINEAR_SCALE = "linear_scale"


# https://huggingface.co/meta-llama/Llama-2-70b-chat-hf


class LanguageModel(Enum):
    GPT4 = "gpt4"
    LLAMA_2_70B_CHAT_HF = "llama-2-70b-chat-hf"
    GEMINI_PRO = "gemini_pro"
    MIXTRAL = "mixtral"
    GPT35Turbo = "gpt35turbo"


class InferenceService(Enum):
    BEDROCK = "bedrock"
    DEEP_INFRA = "deep_infra"
    REPLICATE = "replicate"
    OPENAI = "openai"
