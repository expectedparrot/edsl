"""Train/test splitting functionality for Results objects."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..results import Results
    from ...agents import AgentList
    from ...surveys import Survey


@dataclass
class AgentListSplit:
    """Result of splitting a Results object into train/test AgentLists with corresponding surveys.

    Attributes:
        train: AgentList containing agents with training questions as traits
        test: AgentList containing agents with test questions as traits
        train_survey: Survey object containing only the training questions
        test_survey: Survey object containing only the test questions
    """

    train: "AgentList"
    test: "AgentList"
    train_survey: "Survey"
    test_survey: "Survey"


class ResultsSplitter:
    """Splits a Results object into train/test AgentLists with corresponding surveys.

    Instantiated with a Results object. Provides deterministic (by question name)
    and stochastic (by random selection) splitting strategies.

    Examples:
        >>> from edsl.results import Results
        >>> from edsl.results.extras import ResultsSplitter
        >>> r = Results.example()
        >>> splitter = ResultsSplitter(r)
    """

    def __init__(self, results: "Results") -> None:
        self._results = results

    def split(
        self,
        train_questions: Optional[List[str]] = None,
        test_questions: Optional[List[str]] = None,
        exclude_questions: Optional[List[str]] = None,
        num_questions: Optional[int] = None,
        seed: Optional[int] = None,
    ) -> AgentListSplit:
        """Create an AgentList from the results with a train/test split.

        Args:
            train_questions: Questions to use as TRAIN (deterministic, creates split)
            test_questions: Questions to use as TEST (deterministic, creates split)
            exclude_questions: Questions to fully exclude from both train and test
            num_questions: Number of questions to randomly select for TRAIN (stochastic).
                          If None and no other split parameters are provided, defaults to
                          half of available questions.
            seed: Optional random seed for reproducible random selection (only used
                  with num_questions)

        Returns:
            AgentListSplit with train/test splits and corresponding surveys.

        Raises:
            ResultsError: If survey has skip logic or piping (not supported for splits)

        Examples:
            >>> # Deterministic split - specify train questions
            >>> # split = splitter.split(train_questions=['q1', 'q2'])
            >>> # split.train has q1, q2; split.test has all others
            >>>
            >>> # Deterministic split - specify test questions
            >>> # split = splitter.split(test_questions=['q8', 'q9'])
            >>> # split.train has all others; split.test has q8, q9
            >>>
            >>> # Stochastic split - randomly select 3 questions for train
            >>> # split = splitter.split(num_questions=3, seed=42)
            >>> # split.train has 3 random questions; split.test has remaining
            >>>
            >>> # Default 50/50 split - no parameters specified
            >>> # split = splitter.split(seed=42)
            >>> # split.train has half the questions; split.test has the other half
            >>>
            >>> # Exclude certain questions entirely
            >>> # split = splitter.split(num_questions=3, exclude_questions=['q10'])
        """
        from ...agents import AgentList
        from ..results import ResultsError

        results = self._results

        if len(results.survey.rule_collection.non_default_rules) > 0:
            raise ResultsError(
                "Cannot create agent list splits from surveys with skip logic. "
                "Skip logic creates dependencies between questions that would be broken by splitting."
            )

        piping_pattern = re.compile(r"\{\{.*?\}\}")
        for question in results.survey.questions:
            if piping_pattern.search(question.question_text):
                raise ResultsError(
                    f"Cannot create agent list splits from surveys with piping. "
                    f"Question '{question.question_name}' has piping in its question_text."
                )
            if hasattr(question, "question_options") and question.question_options:
                for option in question.question_options:
                    if isinstance(option, str) and piping_pattern.search(option):
                        raise ResultsError(
                            f"Cannot create agent list splits from surveys with piping. "
                            f"Question '{question.question_name}' has piping in its options."
                        )

        split_params = sum(
            [
                train_questions is not None,
                test_questions is not None,
                num_questions is not None,
            ]
        )
        if split_params > 1:
            raise ValueError(
                "Only one of train_questions, test_questions, or num_questions can be specified"
            )

        all_questions = list(results.survey.question_names)

        if exclude_questions is not None:
            for q in exclude_questions:
                if q not in all_questions:
                    raise ValueError(f"Question {q} not found in survey.")
            all_questions = [q for q in all_questions if q not in exclude_questions]

        if train_questions is not None:
            for q in train_questions:
                if q not in all_questions:
                    raise ValueError(
                        f"Question {q} not found in survey (or was excluded)."
                    )

            train_questions_list = train_questions
            test_questions_list = [
                q for q in all_questions if q not in train_questions_list
            ]

            if not train_questions_list:
                raise ValueError("train_questions resulted in an empty list")
            if not test_questions_list:
                raise ValueError(
                    "No questions left for test split after selecting train questions"
                )

            return AgentListSplit(
                train=AgentList.from_results(results, train_questions_list),
                test=AgentList.from_results(results, test_questions_list),
                train_survey=results.survey.select(*train_questions_list),
                test_survey=results.survey.select(*test_questions_list),
            )

        if test_questions is not None:
            for q in test_questions:
                if q not in all_questions:
                    raise ValueError(
                        f"Question {q} not found in survey (or was excluded)."
                    )

            test_questions_list = test_questions
            train_questions_derived = [
                q for q in all_questions if q not in test_questions_list
            ]

            if not test_questions_list:
                raise ValueError("test_questions resulted in an empty list")
            if not train_questions_derived:
                raise ValueError(
                    "No questions left for train split after selecting test questions"
                )

            return AgentListSplit(
                train=AgentList.from_results(results, train_questions_derived),
                test=AgentList.from_results(results, test_questions_list),
                train_survey=results.survey.select(*train_questions_derived),
                test_survey=results.survey.select(*test_questions_list),
            )

        if num_questions is None:
            num_questions = len(all_questions) // 2

        if num_questions > len(all_questions):
            raise ValueError(
                f"num_questions ({num_questions}) cannot exceed available questions ({len(all_questions)})"
            )

        if seed is not None:
            random.seed(seed)

        train_questions_random = random.sample(all_questions, num_questions)
        test_questions_list = [
            q for q in all_questions if q not in train_questions_random
        ]

        if not test_questions_list:
            raise ValueError("No questions left for test split after random selection")

        return AgentListSplit(
            train=AgentList.from_results(results, train_questions_random),
            test=AgentList.from_results(results, test_questions_list),
            train_survey=results.survey.select(*train_questions_random),
            test_survey=results.survey.select(*test_questions_list),
        )
