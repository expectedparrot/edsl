"""
Optimization Results Module

This module provides the OptimizationResults class for containing and accessing
results from the AgentOptimizer optimization process.
"""



class OptimizationResults:
    """Container for AgentOptimizer results with convenient access methods.

    Attributes
    ----------
    initial_results : Results
        EDSL Results from initial agent evaluation
    initial_comparisons : ResultPairComparisonList
        ResultPairComparisonList from initial evaluation
    target_agents : CandidateAgentList
        CandidateAgentList of agents selected for optimization
    optimized_agents : CandidateAgentList
        CandidateAgentList of optimized agents with new personas
    final_results : Results
        EDSL Results from final evaluation of optimized agents
    final_comparisons : ResultPairComparisonList
        ResultPairComparisonList from final evaluation
    optimization_log : list
        List of detailed optimization steps and suggestions
    optimized_agents_summary : dict
        Convenient summary of optimized agents
    summary : dict
        High-level statistics about the optimization process
    """

    def __init__(self, results_dict: dict):
        """Initialize with results dictionary from AgentOptimizer.optimize()."""
        self.initial_results = results_dict.get("initial_results")
        self.initial_comparisons = results_dict.get("initial_comparisons")
        self.target_agents = results_dict.get("target_agents")
        self.optimized_agents = results_dict.get("optimized_agents")
        self.final_results = results_dict.get("final_results")
        self.final_comparisons = results_dict.get("final_comparisons")
        self.optimization_log = results_dict.get("optimization_log", [])
        self.optimized_agents_summary = results_dict.get("optimized_agents_summary", {})
        self.summary = results_dict.get("summary", {})

    def to_edsl_agent_list(self):
        """Convert optimized agents to an EDSL AgentList object.

        Returns
        -------
        AgentList
            EDSL AgentList containing optimized agents with their improved personas

        Examples
        --------
        >>> results = optimizer.optimize()
        >>> edsl_agents = results.to_edsl_agent_list()
        >>> # Use with EDSL surveys directly
        >>> new_survey = Survey([QuestionYesNo("Are you confident?", "confident")])
        >>> edsl_results = new_survey.by(edsl_agents).run()
        """
        from edsl import Agent, AgentList

        if not self.optimized_agents or not self.optimized_agents.agents:
            return AgentList([])

        # Convert CandidateAgent objects to EDSL Agent objects
        edsl_agents = []
        for candidate_agent in self.optimized_agents.agents:
            edsl_agent = Agent(
                name=candidate_agent.name,
                traits={
                    "persona": candidate_agent.persona,
                },
            )
            edsl_agents.append(edsl_agent)

        return AgentList(edsl_agents)

    def get_optimized_personas(self) -> list[str]:
        """Get list of optimized persona strings.

        Returns
        -------
        list[str]
            List of optimized persona strings
        """
        return [agent.persona for agent in self.optimized_agents.agents]

    def get_optimized_names(self) -> list[str]:
        """Get list of optimized agent names.

        Returns
        -------
        list[str]
            List of optimized agent names
        """
        return [agent.name for agent in self.optimized_agents.agents]

    def get_improvement_details(self) -> list[dict]:
        """Get detailed information about improvements made to each agent.

        Returns
        -------
        list[dict]
            List of dictionaries containing improvement details for each agent
        """
        return self.optimization_log

    def print_summary(self):
        """Print a formatted summary of the optimization results."""
        from rich.console import Console

        console = Console()

        console.print("\n[bold cyan]🎯 OPTIMIZATION SUMMARY[/bold cyan]")
        console.print("=" * 50)
        console.print(f"📊 Initial agents: {self.summary.get('initial_agent_count', 0)}")
        console.print(
            f"🚀 Optimized agents: {self.summary.get('optimized_agent_count', 0)}"
        )
        console.print(f"📈 Success rate: {self.summary.get('improvement_rate', 0):.1%}")

        if self.summary.get("average_perfect_questions"):
            console.print(
                f"⭐ Avg perfect questions: {self.summary.get('average_perfect_questions', 0):.1%}"
            )

        console.print(f"📝 Optimization steps: {len(self.optimization_log)}")

        if self.optimized_agents and self.optimized_agents.agents:
            console.print("\n[bold green]✅ Optimized Agents:[/bold green]")
            for agent in self.optimized_agents.agents:
                console.print(f"  • {agent.name}: {agent.persona[:60]}...")

    def __repr__(self):
        return (
            f"OptimizationResults("
            f"initial_agents={self.summary.get('initial_agent_count', 0)}, "
            f"optimized_agents={self.summary.get('optimized_agent_count', 0)}, "
            f"success_rate={self.summary.get('improvement_rate', 0):.1%})"
        )

    def __len__(self):
        """Return number of optimized agents."""
        return self.summary.get("optimized_agent_count", 0)


__all__ = ["OptimizationResults"]
