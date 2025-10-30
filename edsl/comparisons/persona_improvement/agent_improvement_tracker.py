"""AgentImprovementTracker class for tracking individual agent improvement over iterations."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...comparisons import ResultPairComparison
    from ...agents import Agent

from ..iteration_evaluator import IterationEvaluator
from ..improvement_history_tracker import ImprovementHistoryTracker


class AgentImprovementTracker:
    """Helper class to track improvement state for a single agent."""
    
    def __init__(self, initial_comparison: 'ResultPairComparison', max_no_improvement: int = 2):
        """Initialize with the initial comparison for this agent.
        
        Args:
            initial_comparison: The starting ResultPairComparison for this agent
            max_no_improvement: Number of consecutive non-improvements before stopping
        """
        self.agent_name = initial_comparison.result_A.agent.name
        self.first_comparison = initial_comparison
        self.best_comparison = initial_comparison
        self.best_agent = initial_comparison.result_A.agent
        self.improvement_tracker = ImprovementHistoryTracker()
        self.is_active = True
        self.consecutive_no_improvement = 0
        self.max_no_improvement = max_no_improvement
        self.stopped_at_iteration = None
    
    def update_if_improved(
        self, 
        candidate_comparison: 'ResultPairComparison', 
        candidate_agent: 'Agent', 
        iteration: int
    ) -> bool:
        """Evaluate candidate and update if it's an improvement.
        
        Args:
            candidate_comparison: The new candidate comparison to evaluate
            candidate_agent: The new candidate agent
            iteration: Current iteration number
            
        Returns:
            bool: True if this was an improvement, False otherwise
        """
        evaluator = IterationEvaluator(
            best_comparison=self.best_comparison,
            candidate_comparison=candidate_comparison
        )
        
        result = evaluator.evaluate()
        self.improvement_tracker.record_iteration(result, iteration)
        
        if result.is_improvement:
            self.best_comparison = candidate_comparison
            self.best_agent = candidate_agent
            self.consecutive_no_improvement = 0
            return True
        else:
            self.consecutive_no_improvement += 1
            # Check if we should stop trying to improve this agent
            if self.consecutive_no_improvement >= self.max_no_improvement:
                self.is_active = False
                self.stopped_at_iteration = iteration
            return False
    
    def finalize(self):
        """Finalize tracking by setting first and best comparisons."""
        self.improvement_tracker.set_comparisons(
            first_comparison=self.first_comparison,
            best_comparison=self.best_comparison,
            agent_name=self.agent_name
        )
    
    def get_total_improvements(self) -> int:
        """Get total number of improvements for this agent."""
        return self.improvement_tracker.get_total_improvements()
    
    def get_total_attempts(self) -> int:
        """Get total number of improvement attempts for this agent."""
        return self.improvement_tracker.get_total_attempts()

