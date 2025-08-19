"""
This module contains the ResultFromInterview class for converting interview objects to Result objects.

The ResultFromInterview class encapsulates all the logic needed to extract data from an
interview and create a properly structured Result object, including handling of answers,
prompts, model responses, caching information, and metadata.
"""

from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from .result import Result


class ResultFromInterview:
    """Converts interview objects to Result objects.

    This class handles the complex process of extracting all relevant data from an
    interview object and organizing it into the structure expected by a Result object.
    It processes answers, prompts, model responses, caching information, and metadata.
    """

    def __init__(self, interview):
        """Initialize with an interview object."""
        self.interview = interview

    def convert(self) -> "Result":
        """Convert the interview to a Result object."""
        # Copy the valid results to avoid maintaining references
        model_response_objects = (
            list(self.interview.valid_results)
            if hasattr(self.interview, "valid_results")
            else []
        )

        # Create a copy of the answers
        extracted_answers = (
            dict(self.interview.answers) if hasattr(self.interview, "answers") else {}
        )

        # Save essential information from the interview before clearing references
        agent_copy = (
            self.interview.agent.copy() if hasattr(self.interview, "agent") else None
        )
        scenario_copy = (
            self.interview.scenario.copy()
            if hasattr(self.interview, "scenario")
            else None
        )
        model_copy = (
            self.interview.model.copy() if hasattr(self.interview, "model") else None
        )
        iteration = (
            self.interview.iteration if hasattr(self.interview, "iteration") else 0
        )
        survey_copy = (
            self.interview.survey.copy()
            if hasattr(self.interview, "survey") and self.interview.survey
            else None
        )
        indices_copy = (
            dict(self.interview.indices)
            if hasattr(self.interview, "indices") and self.interview.indices
            else None
        )
        initial_hash = (
            self.interview.initial_hash
            if hasattr(self.interview, "initial_hash")
            else hash(self.interview)
        )

        # Process data to create dictionaries needed for Result
        question_results = self._get_question_results(model_response_objects)
        answer_key_names = list(question_results.keys())

        generated_tokens_dict = (
            self._get_generated_tokens_dict(answer_key_names, question_results)
            if answer_key_names
            else {}
        )
        comments_dict = (
            self._get_comments_dict(answer_key_names, question_results)
            if answer_key_names
            else {}
        )
        reasoning_summaries_dict = (
            self._get_reasoning_summaries_dict(answer_key_names, question_results)
            if answer_key_names
            else {}
        )

        # Get answers that are in the question results
        answer_dict = {}
        for k in answer_key_names:
            if k in extracted_answers:
                answer_dict[k] = extracted_answers[k]

        cache_keys = self._get_cache_keys(model_response_objects)

        question_name_to_prompts = self._get_question_name_to_prompts(
            model_response_objects
        )
        prompt_dictionary = (
            self._get_prompt_dictionary(answer_key_names, question_name_to_prompts)
            if answer_key_names
            else {}
        )

        raw_model_results_dictionary, cache_used_dictionary = (
            self._get_raw_model_results_and_cache_used_dictionary(
                model_response_objects
            )
        )

        validated_dictionary = self._get_validated_dictionary(model_response_objects)

        # Import Result here to avoid circular imports
        from .result import Result

        # Create the Result object with all copied data
        result = Result(
            agent=agent_copy,
            scenario=scenario_copy,
            model=model_copy,
            iteration=iteration,
            answer=answer_dict,
            prompt=prompt_dictionary,
            raw_model_response=raw_model_results_dictionary,
            survey=survey_copy,
            generated_tokens=generated_tokens_dict,
            comments_dict=comments_dict,
            reasoning_summaries_dict=reasoning_summaries_dict,
            cache_used_dict=cache_used_dictionary,
            indices=indices_copy,
            cache_keys=cache_keys,
            validated_dict=validated_dictionary,
        )

        # Store only the hash, not the interview
        result.interview_hash = initial_hash

        # Clear references to help garbage collection of the interview
        if hasattr(self.interview, "clear_references"):
            self.interview.clear_references()

        # Clear local references to help with garbage collection
        del model_response_objects
        del extracted_answers
        del question_results
        del answer_key_names
        del question_name_to_prompts

        return result

    def _get_question_results(self, model_response_objects) -> Dict[str, Any]:
        """Maps the question name to the EDSLResultObjectInput."""
        question_results = {}
        for result in model_response_objects:
            question_results[result.question_name] = result
        return question_results

    def _get_cache_keys(self, model_response_objects) -> Dict[str, bool]:
        """Extract cache keys from model response objects."""
        cache_keys = {}
        for result in model_response_objects:
            cache_keys[result.question_name] = result.cache_key
        return cache_keys

    def _get_generated_tokens_dict(
        self, answer_key_names, question_results
    ) -> Dict[str, str]:
        """Create dictionary of generated tokens for each question."""
        generated_tokens_dict = {
            k + "_generated_tokens": question_results[k].generated_tokens
            for k in answer_key_names
        }
        return generated_tokens_dict

    def _get_comments_dict(self, answer_key_names, question_results) -> Dict[str, str]:
        """Create dictionary of comments for each question."""
        comments_dict = {
            k + "_comment": question_results[k].comment for k in answer_key_names
        }
        return comments_dict

    def _get_reasoning_summaries_dict(
        self, answer_key_names, question_results
    ) -> Dict[str, Any]:
        """Create dictionary of reasoning summaries for each question."""
        reasoning_summaries_dict = {}
        for k in answer_key_names:
            reasoning_summary = question_results[k].reasoning_summary

            # If reasoning summary is None but we have a raw model response, try to extract it
            if reasoning_summary is None and hasattr(
                question_results[k], "raw_model_response"
            ):
                reasoning_summary = self._extract_reasoning_summary(question_results[k])

            reasoning_summaries_dict[k + "_reasoning_summary"] = reasoning_summary
        return reasoning_summaries_dict

    def _extract_reasoning_summary(self, question_result):
        """Try to extract reasoning summary from raw model response."""
        try:
            # Get the model class to access the reasoning_sequence
            model_class = (
                self.interview.model.__class__
                if hasattr(self.interview, "model")
                else None
            )

            if model_class and hasattr(model_class, "reasoning_sequence"):
                from ..language_models.raw_response_handler import RawResponseHandler

                # Create a handler with the model's reasoning sequence
                handler = RawResponseHandler(
                    key_sequence=(
                        model_class.key_sequence
                        if hasattr(model_class, "key_sequence")
                        else None
                    ),
                    usage_sequence=(
                        model_class.usage_sequence
                        if hasattr(model_class, "usage_sequence")
                        else None
                    ),
                    reasoning_sequence=model_class.reasoning_sequence,
                )

                # Try to extract the reasoning summary
                return handler.get_reasoning_summary(question_result.raw_model_response)
        except Exception:
            # If extraction fails, return None
            pass
        return None

    def _get_question_name_to_prompts(
        self, model_response_objects
    ) -> Dict[str, Dict[str, str]]:
        """Create mapping of question names to their prompts."""
        question_name_to_prompts = {}
        for result in model_response_objects:
            question_name = result.question_name
            question_name_to_prompts[question_name] = {
                "user_prompt": result.prompts["user_prompt"],
                "system_prompt": result.prompts["system_prompt"],
            }
        return question_name_to_prompts

    def _get_prompt_dictionary(self, answer_key_names, question_name_to_prompts):
        """Create dictionary of prompts for each question."""
        prompt_dictionary = {}
        for answer_key_name in answer_key_names:
            prompt_dictionary[answer_key_name + "_user_prompt"] = (
                question_name_to_prompts[answer_key_name]["user_prompt"]
            )
            prompt_dictionary[answer_key_name + "_system_prompt"] = (
                question_name_to_prompts[answer_key_name]["system_prompt"]
            )
        return prompt_dictionary

    def _get_raw_model_results_and_cache_used_dictionary(self, model_response_objects):
        """Extract raw model results and cache usage information."""
        raw_model_results_dictionary = {}
        cache_used_dictionary = {}
        for result in model_response_objects:
            question_name = result.question_name
            raw_model_results_dictionary[question_name + "_raw_model_response"] = (
                result.raw_model_response
            )
            raw_model_results_dictionary[question_name + "_input_tokens"] = (
                result.input_tokens
            )
            raw_model_results_dictionary[question_name + "_output_tokens"] = (
                result.output_tokens
            )
            raw_model_results_dictionary[
                question_name + "_input_price_per_million_tokens"
            ] = result.input_price_per_million_tokens
            raw_model_results_dictionary[
                question_name + "_output_price_per_million_tokens"
            ] = result.output_price_per_million_tokens
            raw_model_results_dictionary[question_name + "_cost"] = result.total_cost
            one_usd_buys = (
                "NA"
                if isinstance(result.total_cost, str)
                or result.total_cost == 0
                or result.total_cost is None
                else 1.0 / result.total_cost
            )
            raw_model_results_dictionary[question_name + "_one_usd_buys"] = one_usd_buys
            cache_used_dictionary[question_name] = result.cache_used

        return raw_model_results_dictionary, cache_used_dictionary

    def _get_validated_dictionary(self, model_response_objects):
        """Create dictionary of validation information for each question."""
        validated_dict = {}
        for result in model_response_objects:
            validated_dict[f"{result.question_name}_validated"] = result.validated
        return validated_dict
