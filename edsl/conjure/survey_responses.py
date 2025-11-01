from typing import Dict, List
from collections import UserDict


class SurveyResponses(UserDict):
    def __init__(self, responses: Dict[str, List[str]]):
        super().__init__(responses)
