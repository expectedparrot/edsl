from typing import Optional, Sequence
from .app import App
from ..questions import QuestionMultipleChoice


def create_ranking_app(
    ranking_question: QuestionMultipleChoice,
    option_fields: Sequence[str],
    application_name: Optional[str] = None,
    description: Optional[str] = None,
    option_base: Optional[str] = None,
    rank_field: str = "rank",
    max_pairwise_count: int = 500,
):
    """Deprecated: use App.create_ranking_app instead.

    Thin wrapper maintained for compatibility; forwards to App.create_ranking_app.
    """
    return App.create_ranking_app(
        ranking_question=ranking_question,
        option_fields=option_fields,
        application_name=application_name,
        description=description,
        option_base=option_base,
        rank_field=rank_field,
        max_pairwise_count=max_pairwise_count,
    )

if __name__ == "__main__":
    pass
