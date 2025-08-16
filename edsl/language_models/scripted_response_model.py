"""Scripted Response Language Model for testing scenarios.

This module provides the ScriptedResponseLanguageModel class, which allows creating
language models that return predetermined responses based on agent name and question name
combinations. This is particularly useful for testing scenarios where you want to control
exactly how different agents respond to different questions.
"""

from __future__ import annotations
from typing import Any, Optional, TYPE_CHECKING

from .language_model import LanguageModel

if TYPE_CHECKING:
    from ..invigilators import InvigilatorBase


class ScriptedResponseLanguageModel(LanguageModel):
    """A specialized language model that returns scripted responses based on agent and question names.
    
    This model is designed for testing scenarios where you want to control exactly
    how different agents respond to different questions. It looks up responses using
    the invigilator's agent name and question name.
    
    Examples:
        Create a model with scripted responses for different agents:
        
        >>> responses = {
        ...     'alice': {'favorite_color': 'blue', 'age': '25'},
        ...     'bob': {'favorite_color': 'red', 'age': '30'}
        ... }
        >>> model = ScriptedResponseLanguageModel(responses)
        >>> isinstance(model, LanguageModel)
        True
    """
    
    _model_ = "scripted"
    _inference_service_ = "test"
    _parameters_ = {}  # No parameters needed for scripted responses
    key_sequence = ["message", 0, "text"]
    input_token_name = "prompt_tokens"
    output_token_name = "completion_tokens"
    
    def __init__(self, agent_question_responses: dict[str, dict[str, str]]):
        """Initialize the scripted response model.
        
        Args:
            agent_question_responses: Nested dictionary mapping agent names to question names
                to responses. Format: {'agent_name': {'question_name': 'response'}}
        """
        # Initialize with minimal parameters to avoid API key requirements
        super().__init__(skip_api_key_check=True)
        self.agent_question_responses = agent_question_responses
        
    async def async_execute_model_call(
        self,
        user_prompt: str,
        system_prompt: str,
        question_name: Optional[str] = None,
        invigilator: Optional["InvigilatorBase"] = None,
        **kwargs
    ) -> dict[str, Any]:
        """Execute the model call by looking up the scripted response.
        
        Args:
            user_prompt: The user message (not used for scripted responses)
            system_prompt: The system message (not used for scripted responses)
            question_name: Optional question name (fallback if invigilator not available)
            invigilator: The invigilator containing agent and question information
            **kwargs: Additional arguments (ignored)
            
        Returns:
            dict: Model response with the scripted answer
            
        Raises:
            ValueError: If no scripted response is found for the agent-question combination
        """
        # Extract agent name and question name from invigilator
        if invigilator is not None:
            agent_name = invigilator.agent.name
            question_name = invigilator.question.question_name
        else:
            # Fallback if no invigilator provided
            agent_name = "default"
            if question_name is None:
                question_name = "default"
        
        # Look up the scripted response
        agent_responses = self.agent_question_responses.get(agent_name, {})
        response_text = agent_responses.get(question_name)
        
        if response_text is None:
            # Try to find a more helpful error message
            available_agents = list(self.agent_question_responses.keys())
            if agent_name not in self.agent_question_responses:
                raise ValueError(
                    f"No scripted responses found for agent '{agent_name}'. "
                    f"Available agents: {available_agents}"
                )
            else:
                available_questions = list(agent_responses.keys())
                raise ValueError(
                    f"No scripted response found for agent '{agent_name}' and question '{question_name}'. "
                    f"Available questions for this agent: {available_questions}"
                )
        
        # Return the response in the expected format
        return {
            "message": [{"text": response_text}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
