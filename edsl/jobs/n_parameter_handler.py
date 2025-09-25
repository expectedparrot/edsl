"""
Handler for native n parameter support in language models.

This module implements John Horton's approach: intercepting the run(n=...) parameter
and using native API support for multiple completions when available.
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import asyncio


@dataclass
class ModelNSupport:
    """Defines n parameter support for a model."""
    
    supports_n: bool
    parameter_name: str  # 'n' for OpenAI, 'candidateCount' for Google
    max_value: int
    
    
# Define which models support native n parameter
MODEL_N_SUPPORT = {
    "openai": ModelNSupport(supports_n=True, parameter_name="n", max_value=128),
    "azure": ModelNSupport(supports_n=True, parameter_name="n", max_value=128),
    "google": ModelNSupport(supports_n=True, parameter_name="candidateCount", max_value=8),
    "anthropic": ModelNSupport(supports_n=False, parameter_name="", max_value=1),
    "together": ModelNSupport(supports_n=False, parameter_name="", max_value=1),
    "groq": ModelNSupport(supports_n=False, parameter_name="", max_value=1),
    "mistral": ModelNSupport(supports_n=False, parameter_name="", max_value=1),
    "test": ModelNSupport(supports_n=False, parameter_name="", max_value=1),
}


class NParameterHandler:
    """Handles n parameter logic for Jobs run() method."""
    
    @staticmethod
    def should_use_native_n(model, n: int) -> bool:
        """
        Determine if we should use native n parameter support.
        
        Args:
            model: The language model being used
            n: The requested number of iterations
            
        Returns:
            True if we should use native n parameter, False otherwise
        """
        if n <= 1:
            return False
            
        # Get the model's service name
        service_name = getattr(model, "_inference_service_", "unknown")
        
        # Check if this service supports n
        support = MODEL_N_SUPPORT.get(service_name)
        if not support or not support.supports_n:
            return False
            
        return True
    
    @staticmethod
    def get_batching_strategy(model, n: int) -> List[Tuple[str, int]]:
        """
        Get the batching strategy for a given model and n value.
        
        Returns a list of (parameter_name, batch_size) tuples.
        
        Args:
            model: The language model being used
            n: The requested number of completions
            
        Returns:
            List of tuples (parameter_name, batch_size) for each batch needed
        """
        service_name = getattr(model, "_inference_service_", "unknown")
        support = MODEL_N_SUPPORT.get(service_name)
        
        if not support or not support.supports_n:
            # No native support - return n batches of 1
            return [("", 1) for _ in range(n)]
        
        # Calculate batches based on max_value
        batches = []
        remaining = n
        while remaining > 0:
            batch_size = min(remaining, support.max_value)
            batches.append((support.parameter_name, batch_size))
            remaining -= batch_size
            
        return batches
    
    @staticmethod
    def modify_model_for_n(model, parameter_name: str, n_value: int):
        """
        Create a modified model with the n parameter set.
        
        Args:
            model: The original language model
            parameter_name: The parameter to set ('n' or 'candidateCount')
            n_value: The value to set for the parameter
            
        Returns:
            A modified model with the n parameter set
        """
        # Create a copy of the model with the n parameter
        model_dict = model.to_dict()
        model_dict["parameters"][parameter_name] = n_value
        
        # Import here to avoid circular imports
        from ..language_models import LanguageModel
        
        return LanguageModel.from_dict(model_dict)
    
    @staticmethod
    def extract_multiple_completions(response: Any, n: int) -> List[str]:
        """
        Extract multiple completions from a model response.
        
        Args:
            response: The raw response from the model
            n: The expected number of completions
            
        Returns:
            List of completion strings
        """
        completions = []
        
        # Handle OpenAI-style response
        if hasattr(response, "choices") and response.choices:
            for choice in response.choices[:n]:
                if hasattr(choice, "message") and hasattr(choice.message, "content"):
                    completions.append(choice.message.content)
                elif hasattr(choice, "text"):
                    completions.append(choice.text)
                    
        # Handle Google-style response  
        elif hasattr(response, "candidates") and response.candidates:
            for candidate in response.candidates[:n]:
                if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                    if candidate.content.parts:
                        completions.append(candidate.content.parts[0].text)
                        
        # Handle string response (fallback)
        elif isinstance(response, str):
            completions = [response]
            
        # Pad with empty strings if we didn't get enough completions
        while len(completions) < n:
            completions.append("")
            
        return completions[:n]


class NParameterInterceptor:
    """
    Intercepts interview execution to use native n parameter support.
    
    This class modifies the interview generation process when native n parameter
    support is available, reducing API calls and costs.
    """
    
    def __init__(self, jobs, run_config):
        """
        Initialize the interceptor.
        
        Args:
            jobs: The Jobs instance
            run_config: The RunConfig with n parameter
        """
        self.jobs = jobs
        self.run_config = run_config
        self.handler = NParameterHandler()
        
    def should_intercept(self) -> bool:
        """
        Check if we should intercept the normal interview flow.
        
        Returns:
            True if we should use native n parameter for at least one model
        """
        n = self.run_config.parameters.n
        if n <= 1:
            return False
            
        # Check if any models in the jobs support native n
        for model in self.jobs.models:
            if self.handler.should_use_native_n(model, n):
                return True
                
        return False
    
    async def run_with_native_n(self):
        """
        Run interviews using native n parameter support where available.
        
        This method replaces the normal iteration-based approach with
        native API support for multiple completions.
        """
        # This is a placeholder for the actual implementation
        # The real implementation would need to:
        # 1. Modify the interview runner to pass n to model calls
        # 2. Extract multiple completions from responses
        # 3. Create multiple Result objects from single API calls
        pass