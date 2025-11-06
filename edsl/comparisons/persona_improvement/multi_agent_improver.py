"""MultiAgentImprover class for orchestrating parallel persona improvement across multiple agents."""

from typing import TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
    from ...results import Results
    from ...surveys import Survey
    from ...agents import AgentList

from .agent_improvement_tracker import AgentImprovementTracker
from .persona_improver import PersonaImprover
from ..compare_results_to_gold import CompareResultsToGold


class MultiAgentImprover:
    """Orchestrates iterative improvement for multiple agents in parallel."""

    def __init__(
        self,
        agents: "AgentList",
        gold_results: "Results",
        test_survey: "Survey",
        persona_improver: PersonaImprover = None,
        max_no_improvement: int = 2,
    ):
        """Initialize the multi-agent improver.

        Args:
            agents: AgentList of agents with personas to improve (already generated)
            gold_results: Gold standard results to compare against
            test_survey: Survey to use for testing improved agents
            persona_improver: PersonaImprover instance (creates default if None)
            max_no_improvement: Consecutive non-improvements before stopping an agent
        """
        self.gold_results = gold_results
        self.test_survey = test_survey
        self.persona_improver = persona_improver or PersonaImprover()
        self.current_iteration = 0

        # Use provided agents (assumed to already have personas and proper naming)
        agents_with_personas = agents

        # Run initial evaluation to establish baseline
        initial_results = test_survey.by(agents_with_personas).run()
        initial_comparison_results = CompareResultsToGold(
            initial_results, gold_results, scenario_names={0: "iteration_0_baseline"}
        )

        # Initialize trackers for each agent with their baseline comparison
        self.agent_trackers: Dict[str, AgentImprovementTracker] = {}
        for agent in agents_with_personas:
            agent_name = agent.name
            baseline_comparison = initial_comparison_results.get_comparison_for_agent(
                agent_name, scenario_index=0
            )
            self.agent_trackers[agent_name] = AgentImprovementTracker(
                baseline_comparison, max_no_improvement
            )

    def get_active_agents(self) -> List[str]:
        """Get list of agent names that are still active (not plateaued).

        Returns:
            List of active agent names
        """
        return [
            name for name, tracker in self.agent_trackers.items() if tracker.is_active
        ]

    def generate_candidates_for_active_agents(self) -> "AgentList":
        """Generate improved candidate agents for all active agents.

        Returns:
            AgentList of candidate agents with improved personas
        """
        active_names = self.get_active_agents()
        current_comparisons = [
            self.agent_trackers[name].best_comparison for name in active_names
        ]
        return self.persona_improver.generate_candidates(current_comparisons)

    def evaluate_candidates(
        self, candidate_agents: "AgentList"
    ) -> "CompareResultsToGold":
        """Run test survey with candidates and compare to gold results.

        Args:
            candidate_agents: AgentList of candidates to evaluate

        Returns:
            CompareResultsToGold object with evaluation results
        """
        candidate_test_results = self.test_survey.by(candidate_agents).run()

        return CompareResultsToGold(
            candidate_test_results,
            self.gold_results,
            scenario_names={0: f"iteration_{self.current_iteration}"},
        )

    def update_trackers_with_results(
        self,
        active_agent_names: List[str],
        candidate_comparisons: "CompareResultsToGold",
    ) -> tuple[int, int]:
        """Update each tracker with candidate results and count improvements.

        Args:
            active_agent_names: List of agent names being evaluated
            candidate_comparisons: CompareResultsToGold with evaluation results

        Returns:
            Tuple of (improvements_count, newly_inactive_count)
        """
        improvements_count = 0
        newly_inactive_count = 0

        for agent_idx, agent_name in enumerate(active_agent_names):
            tracker = self.agent_trackers[agent_name]

            # Get comparison for this candidate
            candidate_comparison = candidate_comparisons.get_comparison_for_agent(
                agent_name, scenario_index=0
            )

            # Get the candidate agent from trackers (it was updated during generation)
            # We need to pass the candidate agent that corresponds to this comparison

            candidate_agents_list = list(self.agent_trackers.keys())
            active_idx = candidate_agents_list.index(agent_name)

            was_active_before = tracker.is_active
            is_improvement = tracker.update_if_improved(
                candidate_comparison,
                tracker.best_agent,  # Will be updated if improvement
                self.current_iteration,
            )

            if is_improvement:
                improvements_count += 1
            elif was_active_before and not tracker.is_active:
                newly_inactive_count += 1

        return improvements_count, newly_inactive_count

    def run_iteration(self, iteration_number: int, verbose: bool = True) -> Dict:
        """Run a single iteration of improvement for all active agents.

        Args:
            iteration_number: Current iteration number
            verbose: Whether to print progress information

        Returns:
            Dictionary with iteration statistics
        """
        self.current_iteration = iteration_number

        # Get active agents
        active_agent_names = self.get_active_agents()
        inactive_count = len(self.agent_trackers) - len(active_agent_names)

        if verbose:
            print(
                f"Active agents: {len(active_agent_names)}, Inactive (plateaued): {inactive_count}"
            )

        # Check if we should stop
        if not active_agent_names:
            return {
                "stopped": True,
                "reason": "all_agents_plateaued",
                "active_count": 0,
                "improvements": 0,
            }

        # Generate candidates
        candidate_agents = self.generate_candidates_for_active_agents()

        # Evaluate candidates
        candidate_comparisons = self.evaluate_candidates(candidate_agents)

        # Update trackers with results
        improvements_count = 0
        newly_inactive_count = 0

        for agent_idx, agent_name in enumerate(active_agent_names):
            tracker = self.agent_trackers[agent_name]

            if verbose:
                print(f"\nEvaluating agent: {agent_name[:50]}...")

            # Get comparison for this candidate
            candidate_comparison = candidate_comparisons.get_comparison_for_agent(
                agent_name, scenario_index=0
            )

            was_active_before = tracker.is_active
            is_improvement = tracker.update_if_improved(
                candidate_comparison,
                candidate_agents[agent_idx],
                self.current_iteration,
            )

            if is_improvement:
                if verbose:
                    print(f" - ✓ Improvement for {agent_name[:50]}")
                improvements_count += 1
            else:
                if verbose:
                    print(
                        f" - No improvement for {agent_name[:50]} ({tracker.consecutive_no_improvement}/{tracker.max_no_improvement})"
                    )
                if was_active_before and not tracker.is_active:
                    if verbose:
                        print("   → Agent plateaued, removing from active set")
                    newly_inactive_count += 1

        return {
            "stopped": False,
            "active_count": len(active_agent_names),
            "inactive_count": inactive_count,
            "improvements": improvements_count,
            "newly_inactive": newly_inactive_count,
            "remaining_active": len(active_agent_names) - newly_inactive_count,
        }

    def run_all_iterations(self, num_iterations: int, verbose: bool = True) -> None:
        """Run multiple iterations of improvement until stopping criteria met.

        Args:
            num_iterations: Maximum number of iterations to run
            verbose: Whether to print progress information
        """
        for iteration in range(1, num_iterations + 1):
            if verbose:
                print(f"\n{'='*80}")
                print(f"ITERATION {iteration}")
                print(f"{'='*80}\n")

            stats = self.run_iteration(iteration, verbose=verbose)

            if verbose:
                print(f"\n{'='*80}")
                print(f"ITERATION {iteration} SUMMARY:")
                print(
                    f"  Improvements: {stats['improvements']}/{stats['active_count']}"
                )
                if not stats["stopped"]:
                    print(f"  Newly plateaued: {stats['newly_inactive']}")
                    print(f"  Total active: {stats['remaining_active']}")
                print(f"{'='*80}\n")

            if stats["stopped"]:
                if verbose:
                    print(f"\n{'='*80}")
                    print(
                        f"EARLY STOPPING: {stats['reason'].replace('_', ' ').title()}"
                    )
                    print(f"{'='*80}\n")
                break

    def finalize_all_trackers(self) -> None:
        """Finalize all trackers to prepare for final summary."""
        for tracker in self.agent_trackers.values():
            tracker.finalize()

    def get_best_agents(self) -> "AgentList":
        """Get the best version of each agent after improvement.

        Returns:
            AgentList containing the best version of each agent
        """
        from ...agents import AgentList

        return AgentList(
            [tracker.best_agent for tracker in self.agent_trackers.values()]
        )

    def print_summary(self) -> None:
        """Print detailed summary of improvement process."""
        print(f"\n{'='*80}")
        print("FINAL RESULTS BY AGENT")
        print(f"{'='*80}\n")

        total_improvements = 0
        total_attempts = 0
        agents_with_improvements = 0
        agents_that_plateaued = 0

        for agent_name, tracker in self.agent_trackers.items():
            improvements = tracker.get_total_improvements()
            attempts = tracker.get_total_attempts()
            total_improvements += improvements
            total_attempts += attempts

            if improvements > 0:
                agents_with_improvements += 1
            if not tracker.is_active:
                agents_that_plateaued += 1

            status = (
                "✓ Active"
                if tracker.is_active
                else f"⏸ Plateaued (iter {tracker.stopped_at_iteration})"
            )
            print(f"\nAgent: {agent_name[:70]}")
            print(f"  Status: {status}")
            print(f"  Improvements: {improvements}/{attempts}")
            if improvements > 0:
                print(tracker.improvement_tracker)

        # Overall summary
        print(f"\n{'='*80}")
        print("OVERALL SUMMARY")
        print(f"{'='*80}")
        print(f"Total agents: {len(self.agent_trackers)}")
        print(f"Agents with improvements: {agents_with_improvements}")
        print(f"Agents that plateaued: {agents_that_plateaued}")
        print(f"Total improvements: {total_improvements}/{total_attempts}")
        if total_attempts > 0:
            print(
                f"Overall improvement rate: {total_improvements / total_attempts:.2%}"
            )
        print(f"{'='*80}\n")
