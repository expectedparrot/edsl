"""
Modified async interview runner with native n parameter support.

Implements John Horton's approach: intercepting run(n=...) and using
native API support for multiple completions when available.
"""

from typing import AsyncGenerator, Generator, List, Tuple, Optional
import asyncio
from .async_interview_runner import AsyncInterviewRunner
from .n_parameter_handler import NParameterHandler, MODEL_N_SUPPORT


class AsyncInterviewRunnerWithN(AsyncInterviewRunner):
    """
    Extended interview runner that uses native n parameter support.
    
    When run(n=X) is called with X > 1 and the model supports native
    multiple completions, this runner will:
    1. Make a single API call with n parameter instead of n calls
    2. Extract all completions from the response
    3. Create n results from those completions
    """
    
    def __init__(self, jobs: "Jobs", run_config: "RunConfig"):
        """Initialize with n parameter handler."""
        super().__init__(jobs, run_config)
        self.n_handler = NParameterHandler()
        self._model_n_support = self._analyze_model_support()
        
    def _analyze_model_support(self) -> dict:
        """
        Analyze which models support native n parameter.
        
        Returns:
            Dict mapping model to its n parameter support info
        """
        support_map = {}
        for model in self.jobs.models:
            service_name = getattr(model, "_inference_service_", "unknown")
            support = MODEL_N_SUPPORT.get(service_name)
            support_map[model] = support
        return support_map
    
    def _create_interview_generator(self) -> Generator["Interview", None, None]:
        """
        Create interview generator with n parameter optimization.
        
        This method overrides the parent to implement smart batching:
        - For models supporting native n, yield single interview
        - For models without support, yield n iterations as before
        """
        n = self.run_config.parameters.n
        
        for interview in self.jobs.generate_interviews():
            model = interview.model
            support = self._model_n_support.get(model)
            
            if support and support.supports_n and n > 1:
                # This model supports native n parameter
                # We'll handle multiple completions in the interview itself
                # Mark the interview with metadata about n parameter usage
                interview._use_native_n = True
                interview._n_value = n
                interview._n_parameter_name = support.parameter_name
                interview._n_max_value = support.max_value
                
                # Calculate batching if n exceeds max
                if n <= support.max_value:
                    # Single batch with native n
                    interview._n_batches = [(support.parameter_name, n)]
                    yield interview
                else:
                    # Multiple batches needed
                    batches = self.n_handler.get_batching_strategy(model, n)
                    # Yield one interview per batch
                    for batch_idx, (param_name, batch_size) in enumerate(batches):
                        batch_interview = interview.duplicate(
                            iteration=batch_idx, 
                            cache=self.run_config.environment.cache
                        )
                        batch_interview._use_native_n = True
                        batch_interview._n_value = batch_size
                        batch_interview._n_parameter_name = param_name
                        batch_interview._n_batch_idx = batch_idx
                        yield batch_interview
            else:
                # No native support - use traditional iteration approach
                for iteration in range(n):
                    if iteration > 0:
                        yield interview.duplicate(
                            iteration=iteration, 
                            cache=self.run_config.environment.cache
                        )
                    else:
                        interview.cache = self.run_config.environment.cache
                        interview._use_native_n = False
                        yield interview
    
    async def _process_interview_with_n(
        self, 
        interview: "Interview"
    ) -> List[Tuple["Result", "Interview", int]]:
        """
        Process an interview that uses native n parameter.
        
        This method handles extracting multiple completions from a single
        API call and creating multiple results.
        
        Args:
            interview: Interview marked for native n parameter usage
            
        Returns:
            List of (Result, Interview, iteration) tuples
        """
        # Conduct the interview with modified model
        if hasattr(interview, "_use_native_n") and interview._use_native_n:
            # Modify the model to include n parameter
            original_model = interview.model
            modified_model = self.n_handler.modify_model_for_n(
                original_model,
                interview._n_parameter_name,
                interview._n_value
            )
            interview.model = modified_model
            
            # Conduct the interview (single API call)
            result = await interview.async_conduct_interview(
                config=interview._interview_config
            )
            
            # Extract multiple completions from the result
            # This requires modifying the Result object to handle multiple completions
            results = self._split_result_into_n(result, interview._n_value)
            
            # Create output tuples
            output = []
            base_idx = getattr(interview, "_n_batch_idx", 0) * interview._n_value
            for i, split_result in enumerate(results):
                # Create a duplicate interview for each result
                if i > 0:
                    result_interview = interview.duplicate(
                        iteration=base_idx + i,
                        cache=self.run_config.environment.cache
                    )
                else:
                    result_interview = interview
                    
                output.append((split_result, result_interview, base_idx + i))
                
            # Restore original model
            interview.model = original_model
            
            return output
        else:
            # Traditional single completion
            result = await interview.async_conduct_interview(
                config=interview._interview_config
            )
            return [(result, interview, interview.iteration)]
    
    def _split_result_into_n(self, result: "Result", n: int) -> List["Result"]:
        """
        Split a result containing n completions into n separate results.
        
        This is a placeholder - actual implementation would need to:
        1. Access the raw model response from the result
        2. Extract n completions using NParameterHandler.extract_multiple_completions
        3. Create n Result objects, each with one completion
        
        Args:
            result: Result containing multiple completions
            n: Number of completions to extract
            
        Returns:
            List of n Result objects
        """
        # This would need integration with the Result class
        # For now, return the single result n times (placeholder)
        return [result] * n
    
    async def run(self) -> AsyncGenerator[tuple["Result", "Interview", int], None]:
        """
        Run interviews with native n parameter optimization.
        
        Yields:
            Tuples of (Result, Interview, idx) as interviews complete
        """
        import time
        runner_start = time.time()
        results_count = 0
        
        # Log optimization status
        n = self.run_config.parameters.n
        if n > 1:
            optimized_models = [
                model._model_ for model, support in self._model_n_support.items()
                if support and support.supports_n
            ]
            if optimized_models:
                self._logger.info(
                    f"Using native n={n} parameter for models: {optimized_models}"
                )
            else:
                self._logger.info(
                    f"No models support native n parameter, using iteration approach for n={n}"
                )
        
        # Run the optimized interview process
        interview_gen = self._create_interview_generator()
        
        while True:
            chunk = self._get_next_chunk(interview_gen)
            if not chunk:
                break
                
            # Process chunk with n parameter optimization
            tasks = []
            for idx, interview in chunk:
                if hasattr(interview, "_use_native_n") and interview._use_native_n:
                    # This interview will return multiple results
                    task = asyncio.create_task(
                        self._process_interview_with_n(interview)
                    )
                else:
                    # Traditional single result
                    task = asyncio.create_task(
                        self._run_single_interview_with_idx(interview, idx)
                    )
                tasks.append(task)
            
            # Yield results as they complete
            for coro in asyncio.as_completed(tasks):
                try:
                    result_data = await coro
                    
                    # Handle both single and multiple results
                    if isinstance(result_data, list):
                        # Multiple results from native n parameter
                        for result_tuple in result_data:
                            results_count += 1
                            yield result_tuple
                    else:
                        # Single result
                        results_count += 1
                        yield result_data
                        
                except Exception as e:
                    if self.run_config.parameters.stop_on_exception:
                        raise
                    self._logger.error(f"Interview failed: {e}")
        
        # Log summary
        elapsed = time.time() - runner_start
        self._logger.info(
            f"Completed {results_count} results in {elapsed:.2f}s "
            f"({results_count/elapsed:.1f} results/sec)"
        )
    
    async def _run_single_interview_with_idx(
        self, 
        interview: "Interview", 
        idx: int
    ) -> Tuple["Result", "Interview", int]:
        """
        Run a single interview and return with index.
        
        Args:
            interview: Interview to run
            idx: Original index of the interview
            
        Returns:
            Tuple of (Result, Interview, idx)
        """
        result = await interview.async_conduct_interview(
            config=interview._interview_config
        )
        return (result, interview, idx)