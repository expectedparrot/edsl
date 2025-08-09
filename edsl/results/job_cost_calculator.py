"""Job cost calculation functionality for Results objects.

This module provides the JobCostCalculator class which handles cost computation
for EDSL jobs, including analysis of model response costs and cache usage.
"""

from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from .results import Results
    from .result import Result


class JobCostCalculator:
    """Handles job cost calculation for Results objects.
    
    This class encapsulates all the logic for computing job costs from Results data,
    including handling cached responses, extracting cost information from model
    responses, and providing detailed cost analysis.
    
    Attributes:
        results: The Results object to analyze for cost calculation
    """
    
    def __init__(self, results: "Results"):
        """Initialize the calculator with a Results object.
        
        Args:
            results: The Results object to calculate costs for
        """
        self.results = results
    
    def compute_job_cost(self, include_cached_responses_in_cost: bool = False) -> float:
        """Compute the total cost of a completed job in USD.

        This method calculates the total cost of all model responses in the results.
        By default, it only counts the cost of responses that were not cached.

        Args:
            include_cached_responses_in_cost: Whether to include the cost of cached
                responses in the total. Defaults to False.

        Returns:
            float: The total cost in USD.

        Examples:
            >>> from edsl.results import Results
            >>> from edsl.results.job_cost_calculator import JobCostCalculator
            >>> r = Results.example()
            >>> calculator = JobCostCalculator(r)
            >>> calculator.compute_job_cost()
            0.0
        """
        total_cost = 0.0
        
        for result in self.results:
            total_cost += self._compute_result_cost(
                result, include_cached_responses_in_cost
            )
        
        return total_cost
    
    def _compute_result_cost(
        self, 
        result: "Result", 
        include_cached_responses_in_cost: bool
    ) -> float:
        """Compute the cost for a single Result object.
        
        Args:
            result: The Result object to compute costs for
            include_cached_responses_in_cost: Whether to include cached response costs
            
        Returns:
            float: The cost for this specific result
        """
        result_cost = 0.0
        
        for key in result["raw_model_response"]:
            if key.endswith("_cost"):
                cost_value = result["raw_model_response"][key]
                
                # Extract the question name from the key
                question_name = key.removesuffix("_cost")
                
                # Get cache status safely - default to False if not found
                cache_used = self._get_cache_status(result, question_name)
                
                if isinstance(cost_value, (int, float)):
                    if include_cached_responses_in_cost:
                        result_cost += cost_value
                    elif not include_cached_responses_in_cost and not cache_used:
                        result_cost += cost_value
        
        return result_cost
    
    def _get_cache_status(self, result: "Result", question_name: str) -> bool:
        """Get the cache usage status for a specific question in a result.
        
        Args:
            result: The Result object to check
            question_name: The name of the question to check cache status for
            
        Returns:
            bool: True if the response was cached, False otherwise
        """
        try:
            cache_used_dict = result.get("cache_used_dict", {})
            if hasattr(cache_used_dict, 'get'):
                return cache_used_dict.get(question_name, False)
            elif question_name in cache_used_dict:
                return cache_used_dict[question_name]
        except (KeyError, AttributeError, TypeError):
            pass
        return False
    
    def get_cost_breakdown(self, include_cached_responses_in_cost: bool = False) -> dict:
        """Get a detailed breakdown of costs by question and result.
        
        Args:
            include_cached_responses_in_cost: Whether to include cached response costs
            
        Returns:
            dict: Detailed cost breakdown with the following structure:
                {
                    'total_cost': float,
                    'cached_cost': float,
                    'uncached_cost': float,
                    'by_question': {question_name: cost},
                    'by_result': [{'result_index': int, 'cost': float, 'cached_cost': float}]
                }
        """
        breakdown = {
            'total_cost': 0.0,
            'cached_cost': 0.0,
            'uncached_cost': 0.0,
            'by_question': {},
            'by_result': []
        }
        
        for result_idx, result in enumerate(self.results):
            result_total = 0.0
            result_cached = 0.0
            
            for key in result["raw_model_response"]:
                if key.endswith("_cost"):
                    cost_value = result["raw_model_response"][key]
                    question_name = key.removesuffix("_cost")
                    cache_used = self._get_cache_status(result, question_name)
                    
                    if isinstance(cost_value, (int, float)):
                        # Track by question
                        if question_name not in breakdown['by_question']:
                            breakdown['by_question'][question_name] = 0.0
                        
                        if include_cached_responses_in_cost:
                            breakdown['by_question'][question_name] += cost_value
                            result_total += cost_value
                        elif not cache_used:
                            breakdown['by_question'][question_name] += cost_value
                            result_total += cost_value
                        
                        # Track cached vs uncached
                        if cache_used:
                            breakdown['cached_cost'] += cost_value
                            result_cached += cost_value
                        else:
                            breakdown['uncached_cost'] += cost_value
            
            breakdown['by_result'].append({
                'result_index': result_idx,
                'cost': result_total,
                'cached_cost': result_cached
            })
        
        breakdown['total_cost'] = self.compute_job_cost(include_cached_responses_in_cost)
        return breakdown
    
    def get_cost_summary(self) -> dict:
        """Get a high-level summary of job costs.
        
        Returns:
            dict: Summary with total costs, cache savings, and statistics
        """
        total_with_cache = self.compute_job_cost(include_cached_responses_in_cost=True)
        total_without_cache = self.compute_job_cost(include_cached_responses_in_cost=False)
        cache_savings = total_with_cache - total_without_cache
        
        return {
            'total_cost_including_cache': total_with_cache,
            'total_cost_excluding_cache': total_without_cache,
            'cache_savings': cache_savings,
            'cache_savings_percentage': (cache_savings / total_with_cache * 100) if total_with_cache > 0 else 0.0,
            'num_results': len(self.results),
            'avg_cost_per_result': total_without_cache / len(self.results) if len(self.results) > 0 else 0.0
        } 