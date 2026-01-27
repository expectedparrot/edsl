"""Game engine for Two Truths and a Lie.

This module orchestrates the execution of a single game round.
"""

import time
import random
from typing import List, Dict, Optional, Tuple

from .config.schema import GameConfig, ConditionConfig, ModelConfig
from .models import (
    Storyteller, Judge, Story, Question, Answer,
    QAExchange, Verdict, IntermediateGuess, Round, RoundSetup, RoundOutcome
)
from .facts.database import Fact, FactDatabase, get_default_facts
from .prompts import (
    TruthTellerPrompt, FibberPrompt, StorytellerAnswerPrompt,
    JudgeReviewPrompt, JudgeQuestionPrompt, JudgeVerdictPrompt, JudgeIntermediateGuessPrompt
)
from .edsl_adapter import EDSLAdapter
from .logging_config import get_logger, RoundLoggerAdapter


logger = get_logger("engine")


class GameEngine:
    """Orchestrates a single round of the Two Truths and a Lie game."""

    def __init__(
        self,
        config: GameConfig,
        edsl_adapter: EDSLAdapter,
        fact_database: Optional[FactDatabase] = None
    ):
        """Initialize the game engine.

        Args:
            config: Game configuration
            edsl_adapter: EDSL adapter for model interactions
            fact_database: Database of facts (uses default if not provided)
        """
        self.config = config
        self.edsl = edsl_adapter
        self.facts = fact_database or get_default_facts()

    def setup_round(
        self,
        condition: ConditionConfig,
        fact_category: Optional[str] = None
    ) -> RoundSetup:
        """Set up a new round with assigned roles and facts.

        Args:
            condition: Experimental condition for this round
            fact_category: Category of facts to use (defaults to condition setting)

        Returns:
            RoundSetup with all assignments made
        """
        # Use explicit fact_category if provided, otherwise use condition's setting
        # Note: None is a valid value meaning "random selection across all categories"
        category = fact_category if fact_category is not None else condition.fact_category

        # Get facts for truth-tellers
        num_truth_tellers = condition.game.num_truth_tellers
        num_fibbers = condition.game.num_fibbers

        # Select facts for truth-tellers
        if num_truth_tellers > 0:
            facts = self.facts.get_random_facts(num_truth_tellers, category=category)
        else:
            facts = []

        # Create storytellers
        storytellers: List[Storyteller] = []
        storyteller_ids = ["A", "B", "C"][:condition.game.num_storytellers]

        # Shuffle to randomize who gets which role
        random.shuffle(storyteller_ids)

        for i, sid in enumerate(storyteller_ids):
            if i < num_truth_tellers:
                # Truth-teller
                storytellers.append(Storyteller(
                    id=sid,
                    model=condition.storyteller_model.name,
                    role="truth_teller",
                    strategy=condition.storyteller_strategy,
                    fact_id=facts[i].id
                ))
            else:
                # Fibber
                storytellers.append(Storyteller(
                    id=sid,
                    model=condition.storyteller_model.name,
                    role="fibber",
                    strategy=condition.storyteller_strategy,
                    fact_id=None
                ))

        # Sort back by ID for consistent ordering
        storytellers.sort(key=lambda s: s.id)

        # Create judge
        judge = Judge(
            model=condition.judge_model.name,
            temperature=condition.judge_model.temperature,
            question_style=condition.judge_question_style
        )

        # Create setup
        setup = RoundSetup.create(
            storytellers=storytellers,
            judge=judge,
            fact_category=category,
            condition_id=None  # Can be set externally
        )

        logger.info(f"Round {setup.round_id} setup complete")
        logger.info(f"  Storytellers: {[s.id + '(' + s.role[:1] + ')' for s in storytellers]}")
        logger.info(f"  Story order: {setup.story_order}")

        return setup

    def execute_story_phase(
        self,
        setup: RoundSetup,
        condition: ConditionConfig
    ) -> List[Story]:
        """Execute the story generation phase.

        Args:
            setup: Round setup with storyteller assignments
            condition: Experimental condition

        Returns:
            List of generated stories
        """
        logger.info(f"Round {setup.round_id}: Starting story phase")
        stories: List[Story] = []

        for storyteller in setup.storytellers:
            # Build the appropriate prompt
            if storyteller.is_truth_teller:
                fact = self.facts.get_fact(storyteller.fact_id)
                prompt = TruthTellerPrompt(
                    fact=fact,
                    strategy=storyteller.strategy,
                    word_min=condition.game.story_word_min,
                    word_max=condition.game.story_word_max
                )
            else:
                prompt = FibberPrompt(
                    category=setup.fact_category,
                    strategy=storyteller.strategy,
                    word_min=condition.game.story_word_min,
                    word_max=condition.game.story_word_max
                )

            # Generate the story
            result = self.edsl.generate_story(
                prompt_text=prompt.render(),
                model_name=storyteller.model,
                temperature=condition.storyteller_model.temperature,
                storyteller_id=storyteller.id
            )

            story = Story.create(
                storyteller_id=storyteller.id,
                content=result["content"],
                source_cited=result.get("source_cited"),
                generation_metadata={
                    "latency_ms": result.get("latency_ms"),
                    "model": result.get("model"),
                    "raw_response": result.get("raw_response")
                }
            )

            stories.append(story)
            logger.info(
                f"  Storyteller {storyteller.id} ({storyteller.role}): "
                f"{story.word_count} words"
            )

        return stories

    def execute_qa_phase(
        self,
        setup: RoundSetup,
        stories: List[Story],
        condition: ConditionConfig
    ) -> Tuple[List[QAExchange], List[IntermediateGuess]]:
        """Execute the Q&A phase with intermediate guesses.

        Args:
            setup: Round setup
            stories: Generated stories
            condition: Experimental condition

        Returns:
            Tuple of (Q&A exchanges, intermediate guesses after each exchange)
        """
        logger.info(f"Round {setup.round_id}: Starting Q&A phase with intermediate guesses")

        # Build story lookup
        story_by_id = {s.storyteller_id: s for s in stories}

        # Build stories dict in presentation order
        stories_for_judge = {
            sid: story_by_id[sid].content
            for sid in setup.story_order
        }

        qa_exchanges: List[QAExchange] = []
        intermediate_guesses: List[IntermediateGuess] = []

        # Track Q&A by storyteller for intermediate guess prompts
        qa_by_storyteller: Dict[str, List[Dict[str, str]]] = {sid: [] for sid in setup.story_order}

        # Cumulative Q&A counter for intermediate guesses
        qa_count = 0

        # For each storyteller, ask questions
        for storyteller_id in setup.story_order:
            storyteller = setup.get_storyteller(storyteller_id)
            story = story_by_id[storyteller_id]
            previous_qa: List[Dict[str, str]] = []

            for q_num in range(1, condition.game.questions_per_storyteller + 1):
                # Generate question
                question_prompt = JudgeQuestionPrompt(
                    target_id=storyteller_id,
                    story_content=story.content,
                    question_number=q_num,
                    total_questions=condition.game.questions_per_storyteller,
                    question_style=setup.judge.question_style,
                    previous_qa=previous_qa
                )

                q_result = self.edsl.generate_question(
                    prompt_text=question_prompt.render(),
                    model_name=setup.judge.model,
                    temperature=setup.judge.temperature,
                    target_storyteller_id=storyteller_id,
                    question_number=q_num
                )

                question = Question(
                    judge_model=setup.judge.model,
                    target_storyteller_id=storyteller_id,
                    content=q_result["content"],
                    question_number=q_num,
                    generation_metadata={
                        "latency_ms": q_result.get("latency_ms"),
                        "raw_response": q_result.get("raw_response")
                    }
                )

                # Generate answer
                answer_prompt = StorytellerAnswerPrompt(
                    story_content=story.content,
                    question=question.content,
                    is_truth_teller=storyteller.is_truth_teller,
                    word_min=condition.game.answer_word_min,
                    word_max=condition.game.answer_word_max
                )

                a_result = self.edsl.generate_answer(
                    prompt_text=answer_prompt.render(),
                    model_name=storyteller.model,
                    temperature=condition.storyteller_model.temperature,
                    storyteller_id=storyteller_id,
                    question_number=q_num
                )

                answer = Answer.create(
                    storyteller_id=storyteller_id,
                    question_number=q_num,
                    content=a_result["content"],
                    generation_metadata={
                        "latency_ms": a_result.get("latency_ms"),
                        "raw_response": a_result.get("raw_response")
                    }
                )

                qa_exchanges.append(QAExchange(question=question, answer=answer))
                qa_by_storyteller[storyteller_id].append({
                    "question": question.content,
                    "answer": answer.content
                })
                previous_qa.append({
                    "question": question.content,
                    "answer": answer.content
                })

                logger.info(
                    f"  Q&A {storyteller_id}-{q_num}: "
                    f"Q={len(question.content.split())}w, A={answer.word_count}w"
                )

                # Generate intermediate guess after this Q&A exchange
                qa_count += 1
                guess_prompt = JudgeIntermediateGuessPrompt(
                    num_qa=qa_count,
                    stories=stories_for_judge,
                    qa_so_far=qa_by_storyteller
                )

                ig_result = self.edsl.generate_intermediate_guess(
                    prompt_text=guess_prompt.render(),
                    model_name=setup.judge.model,
                    temperature=setup.judge.temperature,
                    after_qa_number=qa_count
                )

                intermediate_guess = IntermediateGuess(
                    judge_model=setup.judge.model,
                    after_qa_number=qa_count,
                    accused_id=ig_result["accused_id"],
                    confidence=ig_result["confidence"],
                    reasoning=ig_result.get("reasoning", ""),
                    raw_response=ig_result["raw_response"]
                )

                intermediate_guesses.append(intermediate_guess)
                logger.info(
                    f"  Intermediate guess #{qa_count}: Accused {intermediate_guess.accused_id} "
                    f"(confidence: {intermediate_guess.confidence}/10)"
                )

        return qa_exchanges, intermediate_guesses

    def execute_verdict_phase(
        self,
        setup: RoundSetup,
        stories: List[Story],
        qa_exchanges: List[QAExchange]
    ) -> Verdict:
        """Execute the verdict phase.

        Args:
            setup: Round setup
            stories: Generated stories
            qa_exchanges: All Q&A exchanges

        Returns:
            Judge's verdict
        """
        logger.info(f"Round {setup.round_id}: Starting verdict phase")

        # Build data structures for verdict prompt
        story_by_id = {s.storyteller_id: s for s in stories}
        stories_dict = {
            sid: story_by_id[sid].content
            for sid in setup.story_order
        }

        # Group Q&A by storyteller
        qa_by_storyteller: Dict[str, List[Dict[str, str]]] = {}
        for qa in qa_exchanges:
            sid = qa.question.target_storyteller_id
            if sid not in qa_by_storyteller:
                qa_by_storyteller[sid] = []
            qa_by_storyteller[sid].append({
                "question": qa.question.content,
                "answer": qa.answer.content
            })

        # Generate verdict
        verdict_prompt = JudgeVerdictPrompt(
            stories=stories_dict,
            qa_exchanges=qa_by_storyteller
        )

        v_result = self.edsl.generate_verdict(
            prompt_text=verdict_prompt.render(),
            model_name=setup.judge.model,
            temperature=setup.judge.temperature
        )

        verdict = Verdict(
            judge_model=setup.judge.model,
            accused_id=v_result["accused_id"],
            confidence=v_result["confidence"],
            reasoning=v_result["reasoning"],
            frame_break_attempted=v_result["frame_break_attempted"],
            raw_response=v_result["raw_response"]
        )

        logger.info(
            f"  Verdict: Accused {verdict.accused_id} "
            f"(confidence: {verdict.confidence}/10)"
        )
        if verdict.frame_break_attempted:
            logger.warning("  Judge attempted to break frame!")

        return verdict

    def calculate_outcome(
        self,
        setup: RoundSetup,
        verdict: Verdict
    ) -> RoundOutcome:
        """Calculate the round outcome.

        Args:
            setup: Round setup
            verdict: Judge's verdict

        Returns:
            Calculated outcome
        """
        outcome = RoundOutcome.calculate(setup, verdict)

        if outcome.detection_correct:
            logger.info(f"  Outcome: CORRECT detection")
        else:
            logger.info(
                f"  Outcome: INCORRECT - accused {outcome.accused_id}, "
                f"actual fibber was {outcome.fibber_id}"
            )

        return outcome

    def run_round(self, condition: ConditionConfig) -> Round:
        """Execute a complete round.

        Args:
            condition: Experimental condition for this round

        Returns:
            Complete Round with all data
        """
        start_time = time.time()

        # Setup
        setup = self.setup_round(condition)

        # Story phase
        stories = self.execute_story_phase(setup, condition)

        # Q&A phase (now returns intermediate guesses too)
        qa_exchanges, intermediate_guesses = self.execute_qa_phase(setup, stories, condition)

        # Verdict phase
        verdict = self.execute_verdict_phase(setup, stories, qa_exchanges)

        # Calculate outcome
        outcome = self.calculate_outcome(setup, verdict)

        end_time = time.time()
        duration = end_time - start_time

        # Build complete round
        round_data = Round(
            setup=setup,
            stories=stories,
            qa_exchanges=qa_exchanges,
            intermediate_guesses=intermediate_guesses,
            verdict=verdict,
            outcome=outcome,
            duration_seconds=duration
        )

        logger.info(f"Round {setup.round_id} complete in {duration:.1f}s")
        logger.info(f"  Collected {len(intermediate_guesses)} intermediate guesses")

        return round_data
