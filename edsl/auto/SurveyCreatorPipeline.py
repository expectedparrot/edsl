import random
from typing import Dict, List, Any, TypeVar, Generator, Optional

from textwrap import dedent

# from edsl.language_models.model_interfaces.LanguageModelOpenAIFour import LanguageModelOpenAIFour
from edsl import Model
from edsl.agents.AgentList import AgentList
from edsl.results.Results import Results
from edsl import Agent

from edsl import Scenario
from edsl.surveys.Survey import Survey

from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice
from edsl.questions.QuestionFreeText import QuestionFreeText
from edsl.auto.utilities import gen_pipeline
from edsl.utilities.naming_utilities import sanitize_string


m = Model()
