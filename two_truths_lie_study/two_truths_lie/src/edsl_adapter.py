"""EDSL adapter layer for Two Truths and a Lie game.

This module wraps all EDSL interactions, providing:
- Consistent interface for model interactions
- Retry logic with exponential backoff
- Result parsing into domain objects
- Raw response preservation
- Direct API access for models not supported by EDSL proxy
"""

import os
import re
import time
from pathlib import Path
from typing import Dict, Optional, Tuple
from functools import wraps

from edsl import Agent, Model, QuestionFreeText
from dotenv import load_dotenv

from .config.schema import ModelConfig
from .logging_config import get_logger

# Load environment variables for direct API access
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)


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
        self._anthropic_client = None

    def _should_use_direct_api(self, model_name: str) -> bool:
        """Check if model should use direct API instead of EDSL proxy.

        Args:
            model_name: Name of the model

        Returns:
            True if should use direct API, False otherwise
        """
        # Models that fail with EDSL proxy but work with direct API
        direct_api_models = [
            "claude-opus-4-5-20251101",
            "claude-sonnet-4-5-20250929",
        ]
        return model_name in direct_api_models

    def _get_anthropic_client(self):
        """Get or create Anthropic client for direct API access."""
        if self._anthropic_client is None:
            try:
                import anthropic
                api_key = os.environ.get("ANTHROPIC_API_KEY")
                if not api_key:
                    raise ValueError("ANTHROPIC_API_KEY not found in environment")
                self._anthropic_client = anthropic.Anthropic(api_key=api_key)
                logger.info("Initialized Anthropic client for direct API access")
            except ImportError:
                raise ImportError("anthropic package not installed. Run: pip install anthropic")
        return self._anthropic_client

    def _call_anthropic_direct(
        self,
        prompt_text: str,
        model_name: str,
        temperature: float,
        agent_traits: Optional[Dict] = None
    ) -> Tuple[str, Dict]:
        """Call Anthropic API directly, bypassing EDSL proxy.

        Args:
            prompt_text: The prompt text
            model_name: Claude model name
            temperature: Temperature setting
            agent_traits: Optional agent traits (will be prepended to prompt)

        Returns:
            Tuple of (response_text, metadata)
        """
        logger.info(f"Using direct Anthropic API for {model_name}")

        client = self._get_anthropic_client()

        # If agent traits provided, prepend them to the prompt
        if agent_traits:
            persona = agent_traits.get("persona", "")
            if persona:
                prompt_text = f"{persona}\n\n{prompt_text}"

        start_time = time.time()

        # Call Anthropic API
        message = client.messages.create(
            model=model_name,
            max_tokens=4096,
            temperature=temperature,
            messages=[
                {"role": "user", "content": prompt_text}
            ]
        )

        end_time = time.time()

        response_text = message.content[0].text

        metadata = {
            "model": message.model,
            "usage": {
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens,
            },
            "api_type": "direct_anthropic",
            "duration_seconds": end_time - start_time
        }

        logger.info(f"Direct API call completed in {metadata['duration_seconds']:.2f}s")

        return response_text, metadata

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
        # Check if this model should use direct API instead of EDSL proxy
        effective_model_name = model_name or self.default_config.name
        effective_temperature = temperature if temperature is not None else self.default_config.temperature

        if self._should_use_direct_api(effective_model_name):
            return self._call_anthropic_direct(
                prompt_text=prompt_text,
                model_name=effective_model_name,
                temperature=effective_temperature,
                agent_traits=agent_traits
            )

        # Use EDSL proxy for other models
        model = self._create_model(model_name, temperature)

        question = QuestionFreeText(
            question_text=prompt_text,
            question_name=question_name
        )

        start_time = time.time()

        # Check if this model doesn't work with agent traits
        # Gemini, Llama, GPT-5, o3, and Opus 4.5 models fail with agent traits, so skip them
        effective_model_name = model_name or self.default_config.name
        skip_agent_traits = any([
            "gemini" in effective_model_name.lower(),
            "llama" in effective_model_name.lower(),
            "meta-llama" in effective_model_name.lower(),
            "gpt-5" in effective_model_name.lower(),
            "o3" in effective_model_name.lower(),
            "o1" in effective_model_name.lower(),
            "opus-4-5" in effective_model_name.lower(),
            "claude-opus-4-5" in effective_model_name.lower(),
        ])

        logger.info(f"Model: {effective_model_name}, skip_agent_traits: {skip_agent_traits}, has_agent_traits: {agent_traits is not None}")

        # Some models fail with agent traits, so skip them
        if agent_traits and not skip_agent_traits:
            logger.info("Using agent traits with compatible model")
            agent = self._create_agent(agent_traits)
            results = question.by(agent).by(model).run(
                use_api_proxy=True,
                offload_execution=False,
                progress_bar=False
            )
        else:
            # Either no agent traits or this model doesn't support them
            if skip_agent_traits and agent_traits:
                logger.info(f"Skipping agent traits for incompatible model: {effective_model_name}")
            elif not agent_traits:
                logger.info("No agent traits provided")

            results = question.by(model).run(
                use_api_proxy=True,
                offload_execution=False,
                progress_bar=False
            )

        end_time = time.time()

        # Extract the answer
        answer_key = f"answer.{question_name}"
        response_text = results.select(answer_key).first()

        # Handle None response - this can happen with some models
        if response_text is None:
            logger.warning(f"Model returned None response for {question_name}. Attempting alternative extraction.")

            # Try alternative methods to extract the response
            try:
                # Try getting the raw result
                raw_result = results.to_dict()
                logger.debug(f"Raw results keys: {list(raw_result.keys()) if isinstance(raw_result, dict) else 'not a dict'}")

                # Try different answer key formats
                alternative_keys = [
                    question_name,
                    f"{question_name}.answer",
                    "answer",
                ]

                for alt_key in alternative_keys:
                    try:
                        alt_response = results.select(alt_key).first()
                        if alt_response is not None:
                            logger.info(f"Found response using alternative key: {alt_key}")
                            response_text = alt_response
                            break
                    except:
                        continue
            except Exception as e:
                logger.debug(f"Alternative extraction failed: {e}")

            # If still None, raise an error with more context
            if response_text is None:
                raise ValueError(
                    f"Model {model_name or self.default_config.name} returned None/empty response. "
                    f"Question: {question_name}. This may indicate an API issue or model incompatibility."
                )

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
        # Handle None or empty text
        if text is None:
            raise ValueError("Cannot clean None text - model returned empty response")

        if not isinstance(text, str):
            text = str(text)

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
            r"(?:accused|liar|fibber|lying)[:\s]*(?:storyteller\s*)?([ABC])",
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
            accused_match = re.search(r"ACCUSED[:\s]*(?:storyteller\s*)?([ABC])", text, re.IGNORECASE)

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

    @retry_with_backoff(max_retries=3)
    def generate_intermediate_guess(
        self,
        prompt_text: str,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        after_qa_number: int = 1
    ) -> Dict:
        """Generate an intermediate guess from the judge after some Q&A exchanges.

        This enables tracking one-shot, two-shot, n-shot performance.

        Args:
            prompt_text: The intermediate guess prompt
            model_name: Model to use
            temperature: Temperature setting
            after_qa_number: Number of Q&A exchanges completed

        Returns:
            Dict with keys: accused_id, confidence, reasoning, raw_response, latency_ms

        Raises:
            VerdictParsingError: If parsing fails
        """
        logger.info(f"Generating intermediate guess after {after_qa_number} Q&A exchanges")

        try:
            response_text, metadata = self._run_question(
                prompt_text=prompt_text,
                question_name=f"intermediate_guess_{after_qa_number}",
                model_name=model_name,
                temperature=temperature,
                agent_traits={"role": "judge"}
            )

            # Parse the guess (similar to verdict but simpler)
            parsed = self._parse_intermediate_guess(response_text)

            return {
                **parsed,
                "raw_response": response_text,
                **metadata
            }

        except VerdictParsingError:
            raise
        except Exception as e:
            logger.error(f"Intermediate guess generation failed: {e}")
            raise VerdictParsingError(f"Failed to generate intermediate guess: {e}") from e

    def _parse_intermediate_guess(self, text: str) -> Dict:
        """Parse intermediate guess from LLM response.

        Args:
            text: Raw guess text

        Returns:
            Dict with accused_id, confidence, reasoning

        Raises:
            VerdictParsingError: If parsing fails
        """
        text = text.strip()

        # Extract accused ID (using similar patterns to verdict)
        accused_match = re.search(
            r"(?:current_guess|guess|accused|suspect)[:\s]*([ABC])",
            text,
            re.IGNORECASE
        )
        if not accused_match:
            # Try alternative patterns
            accused_match = re.search(
                r"storyteller\s*([ABC])",
                text,
                re.IGNORECASE
            )

        if not accused_match:
            raise VerdictParsingError(f"Could not parse accused ID from intermediate guess: {text[:200]}")

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

        # Reasoning is optional for intermediate guesses (keep it short)
        reasoning_match = re.search(
            r"(?:reasoning|because)[:\s]*(.+?)(?:\n\n|\Z)",
            text,
            re.IGNORECASE | re.DOTALL
        )
        reasoning = reasoning_match.group(1).strip() if reasoning_match else ""

        return {
            "accused_id": accused_id,
            "confidence": confidence,
            "reasoning": reasoning
        }
