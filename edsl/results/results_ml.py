"""
Results ML (Machine Learning) functionality.

This module provides the ResultsML class which handles machine learning-related
operations for Results objects, including train/test splitting.
"""

from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from . import Results
    from ..agents.agent_list_split import AgentListSplit


class ResultsML:
    """
    Handles machine learning operations for Results objects.

    This class encapsulates methods for ML-related operations on Results objects,
    such as creating train/test splits, providing a clean separation of ML logic
    from the main Results class.

    Access via the `ml` property on Results::

        results.ml.split(train_questions=['q1', 'q2'])
    """

    def __init__(self, results: "Results"):
        """
        Initialize the ResultsML with a Results object.

        Args:
            results: The Results object to perform ML operations on
        """
        self.results = results

    def split(
        self,
        train_questions: Optional[List[str]] = None,
        test_questions: Optional[List[str]] = None,
        exclude_questions: Optional[List[str]] = None,
        num_questions: Optional[int] = None,
        seed: Optional[int] = None,
    ) -> "AgentListSplit":
        """Create an AgentList from the results with a train/test split.

        Args:
            train_questions: Questions to use as TRAIN (deterministic, creates split)
            test_questions: Questions to use as TEST (deterministic, creates split)
            exclude_questions: Questions to fully exclude from both train and test
            num_questions: Number of questions to randomly select for TRAIN (stochastic, creates split).
                          If None and no other split parameters are provided, defaults to half of available questions.
            seed: Optional random seed for reproducible random selection (only used with num_questions)

        Returns:
            AgentListSplit with train/test splits and corresponding surveys.

        Raises:
            ResultsError: If survey has skip logic or piping (not supported for splits)

        Examples:
            >>> # Deterministic split - specify train questions
            >>> # split = results.ml.split(train_questions=['q1', 'q2'])
            >>> # split.train has q1, q2; split.test has all others
            >>>
            >>> # Deterministic split - specify test questions
            >>> # split = results.ml.split(test_questions=['q8', 'q9'])
            >>> # split.train has all others; split.test has q8, q9
            >>>
            >>> # Stochastic split - randomly select 3 questions for train
            >>> # split = results.ml.split(num_questions=3, seed=42)
            >>> # split.train has 3 random questions; split.test has remaining
            >>>
            >>> # Default 50/50 split - no parameters specified
            >>> # split = results.ml.split(seed=42)
            >>> # split.train has half the questions; split.test has the other half
            >>>
            >>> # Exclude certain questions entirely
            >>> # split = results.ml.split(num_questions=3, exclude_questions=['q10'])
        """
        from ..agents import AgentList
        from ..agents.agent_list_split import AgentListSplit
        from .exceptions import ResultsError
        import random
        import re

        # Check if survey has skip logic (non-default rules)
        if len(self.results.survey.rule_collection.non_default_rules) > 0:
            raise ResultsError(
                "Cannot create agent list splits from surveys with skip logic. "
                "Skip logic creates dependencies between questions that would be broken by splitting."
            )

        # Check if survey has piping ({{ }} syntax in question text or options)
        piping_pattern = re.compile(r"\{\{.*?\}\}")
        for question in self.results.survey.questions:
            # Check question text
            if piping_pattern.search(question.question_text):
                raise ResultsError(
                    f"Cannot create agent list splits from surveys with piping. "
                    f"Question '{question.question_name}' has piping in its question_text."
                )
            # Check question options if they exist
            if hasattr(question, "question_options") and question.question_options:
                for option in question.question_options:
                    if isinstance(option, str) and piping_pattern.search(option):
                        raise ResultsError(
                            f"Cannot create agent list splits from surveys with piping. "
                            f"Question '{question.question_name}' has piping in its options."
                        )

        # Ensure only one splitting method is used
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

        all_questions = list(self.results.survey.question_names)

        # Apply exclusions first
        if exclude_questions is not None:
            for q in exclude_questions:
                if q not in all_questions:
                    raise ValueError(f"Question {q} not found in survey.")
            all_questions = [q for q in all_questions if q not in exclude_questions]

        # Case 1: train_questions - these become TRAIN split
        if train_questions is not None:
            # Validate questions exist
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

            train_agent_list = AgentList.from_results(
                self.results, train_questions_list
            )
            test_agent_list = AgentList.from_results(self.results, test_questions_list)

            train_survey = self.results.survey.select(*train_questions_list)
            test_survey = self.results.survey.select(*test_questions_list)

            return AgentListSplit(
                train=train_agent_list,
                test=test_agent_list,
                train_survey=train_survey,
                test_survey=test_survey,
            )

        # Case 2: test_questions - these become TEST split
        if test_questions is not None:
            # Validate questions exist
            for q in test_questions:
                if q not in all_questions:
                    raise ValueError(
                        f"Question {q} not found in survey (or was excluded)."
                    )

            test_questions_list = test_questions
            train_questions = [q for q in all_questions if q not in test_questions_list]

            if not test_questions_list:
                raise ValueError("test_questions resulted in an empty list")
            if not train_questions:
                raise ValueError(
                    "No questions left for train split after selecting test questions"
                )

            train_agent_list = AgentList.from_results(self.results, train_questions)
            test_agent_list = AgentList.from_results(self.results, test_questions_list)

            train_survey = self.results.survey.select(*train_questions)
            test_survey = self.results.survey.select(*test_questions_list)

            return AgentListSplit(
                train=train_agent_list,
                test=test_agent_list,
                train_survey=train_survey,
                test_survey=test_survey,
            )

        # Case 3: num_questions - randomly select for TRAIN split (stochastic)
        # If num_questions is None, default to half of available questions
        if num_questions is None:
            num_questions = len(all_questions) // 2

        if num_questions > len(all_questions):
            raise ValueError(
                f"num_questions ({num_questions}) cannot exceed available questions ({len(all_questions)})"
            )

        # Set seed if provided
        if seed is not None:
            random.seed(seed)

        # Randomly select questions for train split
        train_questions = random.sample(all_questions, num_questions)
        test_questions_list = [q for q in all_questions if q not in train_questions]

        if not test_questions_list:
            raise ValueError("No questions left for test split after random selection")

        train_agent_list = AgentList.from_results(self.results, train_questions)
        test_agent_list = AgentList.from_results(self.results, test_questions_list)

        train_survey = self.results.survey.select(*train_questions)
        test_survey = self.results.survey.select(*test_questions_list)

        return AgentListSplit(
            train=train_agent_list,
            test=test_agent_list,
            train_survey=train_survey,
            test_survey=test_survey,
        )

    def augmented_agents(
        self,
        *fields: str,
        include_existing_traits: bool = False,
        include_codebook: bool = False,
    ) -> "AgentList":
        """Augment the agent list by adding specified fields as new traits.

        Takes field names (similar to the select method) and adds them as new traits
        to the agents in the agent list. This only works when there is a one-to-one
        mapping between agents and results.

        Args:
            *fields: Field names to add as traits. Field identifiers follow the same
                rules as :meth:`select` – they can be specified either as fully-qualified
                names (e.g. ``"answer.how_feeling"``) or by bare attribute name when
                unambiguous.
            include_existing_traits: If True, keep existing traits on the agents.
                If False (default), start with empty traits.
            include_codebook: If True, keep existing codebook on the agents.
                If False (default), reset the codebook.

        Returns:
            AgentList: A new AgentList with the specified fields added as traits.

        Raises:
            ResultsError: If there are multiple observations per agent (e.g., from
                multiple scenarios or models), or if no fields are provided, or if
                an invalid field name is supplied.

        Examples:
            >>> # results.ml.augmented_agents("color", "food")
            >>> # Returns AgentList with color and food as traits
        """
        from ..agents import AgentList
        from .exceptions import ResultsError

        # Check if fields are provided
        if not fields:
            raise ResultsError("At least one field must be specified for augmentation.")

        al = AgentList()
        for result in self.results.data:
            agent = result.get("agent")
            new_agent = agent.copy()
            naming_dict = {"name": new_agent.name}
            if not include_existing_traits:
                new_agent.traits = {}
            if not include_codebook:
                new_agent.codebook = {}
                new_agent.traits_presentation_template = "Your traits: {{traits}}"
            naming_dict["scenario_index"] = result.sub_dicts["scenario"][
                "scenario_index"
            ]
            naming_dict["model_index"] = result.sub_dicts["model"]["model_index"]
            new_agent.traits = {
                k: v for k, v in result.sub_dicts["answer"].items() if k in fields
            }
            new_agent.name = repr(naming_dict)
            al.append(new_agent)
        return al
