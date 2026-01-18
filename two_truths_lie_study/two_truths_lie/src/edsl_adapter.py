"""EDSL adapter layer for Two Truths and a Lie game.

This module wraps all EDSL interactions, providing:
- Consistent interface for model interactions
- Retry logic with exponential backoff
- Result parsing into domain objects
- Raw response preservation
"""

import re
import time
from typing import Dict, Optional, Tuple
from functools import wraps

from edsl import Agent, Model, QuestionFreeText

from .config.schema import ModelConfig
from .logging_config import get_logger


logger = get_logger("edsl_adapter")


class StoryGenerationError(Exception):
    """Error during story generation."""
    pass


class VerdictParsingError(Exception):
    """Error parsing verdict from LLM response."""
    pass


class QuestionGenerationError(Exception):
    """Error during question generation."""
    pass


class AnswerGenerationError(Exception):
    """Error during answer generation."""
    pass


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator for retrying operations with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds (doubles each retry)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(
                            f"Attempt {attempt + 1} failed: {e}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed")
            raise last_error
        return wrapper
    return decorator


class EDSLAdapter:
    """Adapter layer for all EDSL operations."""

    def __init__(self, config: Optional[ModelConfig] = None):
        """Initialize the adapter.

        Args:
            config: Default model configuration
        """
        self.default_config = config or ModelConfig()

    def _create_model(
        self,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> Model:
        """Create an EDSL Model instance.

        Args:
            model_name: Model name (uses default if not specified)
            temperature: Temperature (uses default if not specified)

        Returns:
            Configured Model instance
        """
        name = model_name or self.default_config.name
        temp = temperature if temperature is not None else self.default_config.temperature

        return Model(name, temperature=temp)

    def _create_agent(self, traits: Dict) -> Agent:
        """Create an EDSL Agent instance.

        Args:
            traits: Agent traits dictionary

        Returns:
            Configured Agent instance
        """
        return Agent(traits=traits)

    def _run_question(
        self,
        prompt_text: str,
        question_name: str,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        agent_traits: Optional[Dict] = None
    ) -> Tuple[str, Dict]:
        """Run a single question through EDSL and get the response.

        Args:
            prompt_text: The prompt text
            question_name: Name for the question (for EDSL tracking)
            model_name: Model to use
            temperature: Temperature setting
            agent_traits: Optional agent traits

        Returns:
            Tuple of (response_text, metadata)
        """
        model = self._create_model(model_name, temperature)

        question = QuestionFreeText(
            question_text=prompt_text,
            question_name=question_name
        )

        start_time = time.time()

        if agent_traits:
            agent = self._create_agent(agent_traits)
            results = question.by(agent).by(model).run(
                use_api_proxy=True,
                offload_execution=False,
                progress_bar=False
            )
        else:
            results = question.by(model).run(
                use_api_proxy=True,
                offload_execution=False,
                progress_bar=False
            )

        end_time = time.time()

        # Extract the answer
        answer_key = f"answer.{question_name}"
        response_text = results.select(answer_key).first()

        # Build metadata
        metadata = {
            "latency_ms": int((end_time - start_time) * 1000),
            "model": model_name or self.default_config.name,
            "temperature": temperature if temperature is not None else self.default_config.temperature,
        }

        return response_text, metadata

    @retry_with_backoff(max_retries=3)
    def generate_story(
        self,
        prompt_text: str,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        storyteller_id: str = "unknown"
    ) -> Dict:
        """Generate a story from a storyteller prompt.

        Args:
            prompt_text: The storyteller prompt
            model_name: Model to use
            temperature: Temperature setting
            storyteller_id: ID of the storyteller (for logging)

        Returns:
            Dict with keys: content, raw_response, word_count, latency_ms, source_cited

        Raises:
            StoryGenerationError: If story generation fails
        """
        logger.info(f"Generating story for storyteller {storyteller_id}")

        try:
            response_text, metadata = self._run_question(
                prompt_text=prompt_text,
                question_name=f"story_{storyteller_id}",
                model_name=model_name,
                temperature=temperature,
                agent_traits={"role": "storyteller", "storyteller_id": storyteller_id}
            )

            # Extract source if mentioned (simple heuristic)
            source_cited = self._extract_source(response_text)

            return {
                "content": response_text,
                "raw_response": response_text,
                "word_count": len(response_text.split()),
                "source_cited": source_cited,
                **metadata
            }

        except Exception as e:
            logger.error(f"Story generation failed for {storyteller_id}: {e}")
            raise StoryGenerationError(f"Failed to generate story: {e}") from e

    def _extract_source(self, text: str) -> Optional[str]:
        """Extract source citation from text (simple heuristic).

        Args:
            text: The story text

        Returns:
            Extracted source or None
        """
        # Look for common source patterns
        patterns = [
            r"(?:according to|source:|cited in|published in|from)\s+([^.]+)",
            r"(?:I (?:read|learned|heard) (?:this |about this )?(?:in|from))\s+([^.]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    @retry_with_backoff(max_retries=3)
    def generate_question(
        self,
        prompt_text: str,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        target_storyteller_id: str = "unknown",
        question_number: int = 1
    ) -> Dict:
        """Generate a question from the judge.

        Args:
            prompt_text: The judge question prompt
            model_name: Model to use
            temperature: Temperature setting
            target_storyteller_id: ID of storyteller being questioned
            question_number: Which question this is

        Returns:
            Dict with keys: content, raw_response, latency_ms

        Raises:
            QuestionGenerationError: If question generation fails
        """
        logger.info(
            f"Generating question {question_number} for storyteller {target_storyteller_id}"
        )

        try:
            response_text, metadata = self._run_question(
                prompt_text=prompt_text,
                question_name=f"question_{target_storyteller_id}_{question_number}",
                model_name=model_name,
                temperature=temperature,
                agent_traits={"role": "judge"}
            )

            # Clean up the response (remove any preamble)
            question_text = self._clean_question(response_text)

            return {
                "content": question_text,
                "raw_response": response_text,
                **metadata
            }

        except Exception as e:
            logger.error(f"Question generation failed: {e}")
            raise QuestionGenerationError(f"Failed to generate question: {e}") from e

    def _clean_question(self, text: str) -> str:
        """Clean up question text, removing any preamble.

        Args:
            text: Raw question text

        Returns:
            Cleaned question text
        """
        # Remove common preambles
        text = text.strip()

        # If it starts with quotes, extract the quoted part
        if text.startswith('"') and '"' in text[1:]:
            end_quote = text.index('"', 1)
            return text[1:end_quote]

        # Remove phrases like "My question is:" or "I would ask:"
        preambles = [
            r"^(?:my question (?:is|would be)[:\s]+)",
            r"^(?:i (?:would |want to )?ask[:\s]+)",
            r"^(?:question[:\s]+)",
        ]
        for pattern in preambles:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        return text.strip()

    @retry_with_backoff(max_retries=3)
    def generate_answer(
        self,
        prompt_text: str,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        storyteller_id: str = "unknown",
        question_number: int = 1
    ) -> Dict:
        """Generate an answer from a storyteller.

        Args:
            prompt_text: The answer prompt
            model_name: Model to use
            temperature: Temperature setting
            storyteller_id: ID of the storyteller
            question_number: Which question this answers

        Returns:
            Dict with keys: content, raw_response, word_count, latency_ms

        Raises:
            AnswerGenerationError: If answer generation fails
        """
        logger.info(
            f"Generating answer from storyteller {storyteller_id} "
            f"to question {question_number}"
        )

        try:
            response_text, metadata = self._run_question(
                prompt_text=prompt_text,
                question_name=f"answer_{storyteller_id}_{question_number}",
                model_name=model_name,
                temperature=temperature,
                agent_traits={"role": "storyteller", "storyteller_id": storyteller_id}
            )

            return {
                "content": response_text,
                "raw_response": response_text,
                "word_count": len(response_text.split()),
                **metadata
            }

        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            raise AnswerGenerationError(f"Failed to generate answer: {e}") from e

    @retry_with_backoff(max_retries=3)
    def generate_verdict(
        self,
        prompt_text: str,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> Dict:
        """Generate a verdict from the judge.

        Args:
            prompt_text: The verdict prompt
            model_name: Model to use
            temperature: Temperature setting

        Returns:
            Dict with keys: accused_id, confidence, reasoning, raw_response,
                           frame_break_attempted, latency_ms

        Raises:
            VerdictParsingError: If verdict parsing fails
        """
        logger.info("Generating verdict from judge")

        try:
            response_text, metadata = self._run_question(
                prompt_text=prompt_text,
                question_name="verdict",
                model_name=model_name,
                temperature=temperature,
                agent_traits={"role": "judge"}
            )

            # Parse the verdict
            parsed = self._parse_verdict(response_text)

            return {
                **parsed,
                "raw_response": response_text,
                **metadata
            }

        except VerdictParsingError:
            raise
        except Exception as e:
            logger.error(f"Verdict generation failed: {e}")
            raise VerdictParsingError(f"Failed to generate verdict: {e}") from e

    def _parse_verdict(self, text: str) -> Dict:
        """Parse verdict from LLM response.

        Args:
            text: Raw verdict text

        Returns:
            Dict with accused_id, confidence, reasoning, frame_break_attempted

        Raises:
            VerdictParsingError: If parsing fails
        """
        text = text.strip()

        # Check for frame-breaking (judge refuses to accuse)
        frame_break_patterns = [
            r"cannot (?:determine|identify|accuse)",
            r"all (?:of the )?(?:stories )?(?:seem|appear)(?: to be)? (?:true|genuine)",
            r"none of them (?:seem|appear)",
            r"refuse to (?:accuse|identify)",
        ]
        frame_break_attempted = any(
            re.search(p, text, re.IGNORECASE) for p in frame_break_patterns
        )

        # Extract accused ID
        accused_match = re.search(
            r"(?:accused|liar|fibber|lying)[:\s]*([ABC])",
            text,
            re.IGNORECASE
        )
        if not accused_match:
            # Try alternative patterns
            accused_match = re.search(
                r"storyteller\s*([ABC])\s*(?:is|was|seems)",
                text,
                re.IGNORECASE
            )
        if not accused_match:
            # Last resort: find any standalone A, B, or C after "ACCUSED:"
            accused_match = re.search(r"ACCUSED[:\s]*([ABC])", text, re.IGNORECASE)

        if not accused_match:
            if frame_break_attempted:
                # If frame break, default to A
                accused_id = "A"
            else:
                raise VerdictParsingError(f"Could not parse accused ID from: {text[:200]}")
        else:
            accused_id = accused_match.group(1).upper()

        # Extract confidence
        confidence_match = re.search(
            r"(?:confidence)[:\s]*(\d+)",
            text,
            re.IGNORECASE
        )
        if confidence_match:
            confidence = int(confidence_match.group(1))
            confidence = max(1, min(10, confidence))  # Clamp to 1-10
        else:
            confidence = 5  # Default to middle confidence

        # Extract reasoning
        reasoning_match = re.search(
            r"(?:reasoning|because|reason)[:\s]*(.+?)(?:\n\n|\Z)",
            text,
            re.IGNORECASE | re.DOTALL
        )
        if reasoning_match:
            reasoning = reasoning_match.group(1).strip()
        else:
            # Use the whole text as reasoning
            reasoning = text[:500]

        return {
            "accused_id": accused_id,
            "confidence": confidence,
            "reasoning": reasoning,
            "frame_break_attempted": frame_break_attempted
        }
