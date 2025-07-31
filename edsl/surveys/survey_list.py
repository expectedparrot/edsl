from typing import List, Optional
from ..base import ItemCollection
from ..surveys import Survey

class SurveyList(ItemCollection):

    item_class = Survey

    def combined_survey(self, keep: Optional[List[str]] = None, drop: Optional[List[str]] = None) -> 'Survey':

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
        return len(set(self.question_names)) == len(self.question_names)
    
    @property
    def question_names(self) -> List[str]:
        return [item.question_name for item in self]
