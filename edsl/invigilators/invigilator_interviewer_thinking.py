"""Invigilator for QuestionInterviewerThinking that bypasses normal prompt construction.

This module provides the InvigilatorInterviewerThinking class, which handles the execution
of QuestionInterviewerThinking questions. Unlike other invigilators, this one:
- Bypasses the normal PromptConstructor (no agent persona/instructions)
- Uses the question's embedded model instead of the interview's model
- Uses question_text directly as the user prompt
- Uses system_prompt directly as the system prompt
- Still integrates with the cache system for reproducibility
"""

from __future__ import annotations
from typing import Dict, Any, Optional, TYPE_CHECKING

from jinja2 import Environment

from ..base.data_transfer_models import EDSLResultObjectInput
from .invigilator_base import InvigilatorBase

if TYPE_CHECKING:
    from ..prompts import Prompt
    from ..questions import QuestionBase


class InvigilatorInterviewerThinking(InvigilatorBase):
    """
    Invigilator for QuestionInterviewerThinking that makes direct LLM calls.

    This invigilator bypasses the normal EDSL prompt construction pipeline and instead:
    1. Uses the question's embedded model (not the interview/job's model)
    2. Uses question_text directly as the user prompt (with Jinja2 rendering)
    3. Uses system_prompt directly as the system prompt (with Jinja2 rendering)
    4. Passes through the response without agent-specific processing

    The caching system is still used, so repeated calls with the same prompts
    will return cached results.
    """

    def _render_template(self, template_string: str) -> str:
        """
        Render a Jinja2 template string with the current context.

        This allows question_text and system_prompt to reference previous answers
        using syntax like {{ q1.answer }}.

        Args:
            template_string: The template string to render

        Returns:
            The rendered string with all variables substituted
        """
        if not template_string:
            return ""

        # Build context with scenario and prior answers
        context = {}

        # Add scenario values
        if self.scenario:
            context.update(dict(self.scenario))

        # Add prior answers - need to get them from the survey
        if self.survey and self.current_answers:
            question_dict = self.survey.question_names_to_questions()
            for q_name, question in question_dict.items():
                if q_name in self.current_answers:
                    # Create a simple object that allows .answer access
                    class AnswerHolder:
                        def __init__(self, answer, comment=None):
                            self.answer = answer
                            self.comment = comment

                    answer_value = self.current_answers.get(q_name)
                    comment_value = self.current_answers.get(f"{q_name}_comment")
                    context[q_name] = AnswerHolder(answer_value, comment_value)

        # Render the template
        env = Environment()
        template = env.from_string(template_string)
        return template.render(**context)

    def get_prompts(self) -> Dict[str, "Prompt"]:
        """
        Get the prompts used by this invigilator.

        For InterviewerThinking questions, we use the question's prompts directly
        (after Jinja2 rendering) rather than constructing them through the normal pipeline.

        Returns:
            Dict with 'user_prompt' and 'system_prompt' keys
        """
        from ..prompts import Prompt

        # Render the prompts with Jinja2
        user_prompt = self._render_template(self.question.question_text)
        system_prompt = self._render_template(self.question.system_prompt)

        return {
            "user_prompt": Prompt(user_prompt),
            "system_prompt": Prompt(system_prompt),
        }

    async def async_answer_question(self) -> EDSLResultObjectInput:
        """
        Answer the question using the question's embedded model.

        This method:
        1. Gets the model from the question (not from self.model)
        2. Renders the prompts with Jinja2 templating
        3. Makes the LLM call with optional structured output
        4. Returns the result with pass-through validation

        Returns:
            EDSLResultObjectInput containing the answer and metadata
        """
        # Get the model from the question, not from the interview
        question_model = self.question.get_model()

        # Copy relevant settings from the interview's model to the question's model
        # This ensures that job-level settings (like remote_proxy, remote) are respected
        if self.model is not None:
            if hasattr(self.model, "remote"):
                question_model.remote = self.model.remote
            if hasattr(self.model, "remote_proxy"):
                question_model.remote_proxy = self.model.remote_proxy

        # Get rendered prompts
        prompts = self.get_prompts()
        user_prompt = prompts["user_prompt"].text
        system_prompt = prompts["system_prompt"].text

        # Prepare the call parameters
        params = {
            "user_prompt": user_prompt,
            "system_prompt": system_prompt,
            "iteration": self.iteration,
            "cache": self.cache,
        }

        # Add structured output schema if specified
        if hasattr(self.question, "user_response_model") and self.question.user_response_model is not None:
            params["response_schema"] = self.question.get_response_schema()
            params["response_schema_name"] = self.question.user_response_model.__name__

        # Set up key lookup if available
        if self.key_lookup:
            question_model.set_key_lookup(self.key_lookup)

        # Pass the invigilator for any callbacks
        params["invigilator"] = self

        # Make the LLM call
        try:
            agent_response_dict = await question_model.async_get_response(**params)

            # Store raw response for potential debugging
            self.raw_model_response = agent_response_dict.model_outputs.response

            # Extract the answer
            answer = agent_response_dict.edsl_dict.answer
            generated_tokens = agent_response_dict.edsl_dict.generated_tokens
            comment = agent_response_dict.edsl_dict.comment or ""

            # For structured output, try to parse the JSON
            if hasattr(self.question, "user_response_model") and self.question.user_response_model is not None:
                if isinstance(answer, str):
                    import json
                    try:
                        answer = json.loads(answer)
                    except json.JSONDecodeError:
                        # If parsing fails, keep as string
                        pass

            # Build the result
            data = {
                "answer": answer,
                "comment": comment,
                "generated_tokens": generated_tokens,
                "question_name": self.question.question_name,
                "prompts": prompts,
                "cached_response": agent_response_dict.model_outputs.cached_response,
                "raw_model_response": agent_response_dict.model_outputs.response,
                "cache_used": agent_response_dict.model_outputs.cache_used,
                "cache_key": agent_response_dict.model_outputs.cache_key,
                "validated": True,  # Pass-through validation
                "exception_occurred": None,
                "input_tokens": agent_response_dict.model_outputs.input_tokens,
                "output_tokens": agent_response_dict.model_outputs.output_tokens,
                "input_price_per_million_tokens": agent_response_dict.model_outputs.input_price_per_million_tokens,
                "output_price_per_million_tokens": agent_response_dict.model_outputs.output_price_per_million_tokens,
                "total_cost": agent_response_dict.model_outputs.total_cost,
            }

            return EDSLResultObjectInput(**data)

        except Exception as e:
            # Handle errors gracefully
            data = {
                "answer": None,
                "comment": f"Error during LLM call: {str(e)}",
                "generated_tokens": None,
                "question_name": self.question.question_name,
                "prompts": prompts,
                "cached_response": None,
                "raw_model_response": None,
                "cache_used": None,
                "cache_key": None,
                "validated": False,
                "exception_occurred": e,
            }
            return EDSLResultObjectInput(**data)


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
