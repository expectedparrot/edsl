"""
Agent Optimization Framework

This module provides the AgentOptimizer class for systematically improving EDSL agent personas
based on performance against gold standard answers.
"""

import logging
import sys
from typing import Optional, Union, Literal
from functools import wraps
from rich.console import Console
from rich.table import Table

from .candidate_agent import CandidateAgentList, CandidateAgent
from .prompt_adjust import PromptAdjust
from .factory import ComparisonFactory
from .metrics import ExactMatch, SquaredDistance, Overlap
from .optimization_results import OptimizationResults

# Type literal for agent selection strategies
SelectionStrategy = Literal[
    "all",          # Select all agents for optimization
    "pareto",       # Select non-dominated agents (Pareto frontier) - best across multiple metrics
    "top_percent",  # Select top X% of agents based on a specific metric
    "top_count"     # Select top N agents based on a specific metric
]


def log_method_calls(func):
    """Decorator to log method calls in the optimization sequence.
    
    This decorator logs the entry and exit of methods, helping track
    the sequence of operations during agent optimization.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        method_name = func.__name__
        
        # Log method entry
        self.logger.info(f"→ Starting {method_name}")
        
        try:
            result = func(self, *args, **kwargs)
            # Log successful completion
            self.logger.info(f"✓ Completed {method_name}")
            return result
        except Exception as e:
            # Log any errors
            self.logger.error(f"✗ Error in {method_name}: {e}")
            raise
    
    return wrapper


class AgentOptimizer:
    """
    Manages the complete agent optimization process including analysis, improvement,
    and performance evaluation against gold standards.
    
    Examples
    --------
    >>> from edsl import Survey, QuestionYesNo
    >>> survey = Survey([QuestionYesNo("Are you nervous?", "nervous")])
    >>> gold_dict = {"nervous": "Yes"}
    >>> agents = CandidateAgentList([...])
    >>> 
    >>> optimizer = AgentOptimizer(
    ...     survey=survey,
    ...     gold_standard=gold_dict,
    ...     starting_agents=agents
    ... )
    >>> results = optimizer.optimize(verbose=True)
    """
    
    def __init__(
        self,
        survey,
        gold_standard: dict,
        starting_agents: CandidateAgentList,
        comparison_factory: Optional[ComparisonFactory] = None,
        logger: Optional[logging.Logger] = None,
        console: Optional[Console] = None
    ):
        """Initialize the AgentOptimizer.
        
        Parameters
        ----------
        survey
            EDSL Survey object containing questions to evaluate
        gold_standard
            Dictionary mapping question_name -> expected_answer
        starting_agents
            CandidateAgentList of initial agents to optimize
        comparison_factory
            Optional ComparisonFactory for metrics. If None, uses default metrics.
        logger
            Optional logger instance. If None, creates a default logger.
        console
            Optional Rich Console for output. If None, creates a default console.
        """
        self.survey = survey
        self.gold_standard = gold_standard
        self.starting_agents = starting_agents
        
        # Set up comparison factory
        if comparison_factory is None:
            metrics = [ExactMatch(), SquaredDistance(), Overlap()]
            
            # Try to add CosineSimilarity if sentence-transformers is available
            try:
                from .metrics import CosineSimilarity
                metrics.append(CosineSimilarity())
            except ImportError:
                # sentence-transformers not available, skip cosine similarity
                pass
            
            self.comparison_factory = ComparisonFactory(metrics)
        else:
            self.comparison_factory = comparison_factory
        
        # Set up logging
        if logger is None:
            self.logger = self._setup_default_logger()
        else:
            self.logger = logger
            
        # Set up console for rich output
        if console is None:
            self.console = Console()
        else:
            self.console = console
        
        # Validate inputs
        self._validate_inputs()
        
        # Initialize state
        self.initial_results = None
        self.initial_comparisons = None
        self.optimized_agents = None
        self.final_results = None
        self.final_comparisons = None
        self.optimization_log = []
    
    def _setup_default_logger(self) -> logging.Logger:
        """Set up default logger for the optimization process."""
        logger = logging.getLogger("AgentOptimizer")
        logger.setLevel(logging.INFO)
        
        # Create console handler if not already exists
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _validate_inputs(self):
        """Validate that inputs are properly configured."""
        # Check that gold standard matches survey questions
        survey_questions = set(q.question_name for q in self.survey.questions)
        gold_questions = set(self.gold_standard.keys())
        
        if survey_questions != gold_questions:
            raise ValueError(
                f"Gold standard questions {gold_questions} don't match "
                f"survey questions {survey_questions}"
            )
        
        # Check that all agents have names
        for agent in self.starting_agents.agents:
            if not agent.name:
                raise ValueError("All starting agents must have names")
            
    def _get_display_columns(self, results):
        """Helper to get display columns for results tables."""
        question_columns = ["persona"] + [
            q.question_name for q in self.survey.questions 
            if q.question_name != "persona"
        ]
        # Add comment columns if they exist
        available_columns = set(results.columns)
        comment_columns = [col for col in available_columns if col.startswith("comment.")]
        return question_columns + comment_columns
    
    def evaluate_initial_performance(self, verbose: bool = True) -> tuple:
        """Evaluate initial agent performance against gold standard.
        
        Parameters
        ----------
        verbose
            If True, display detailed output
            
        Returns
        -------
        tuple
            (results, comparisons) from the initial evaluation
        """
        if verbose:
            self.console.print("\n[bold blue]INITIAL PERFORMANCE EVALUATION[/bold blue]")
            self.console.print("="*60)
        
        self.logger.info("Starting initial performance evaluation")
        
        # Run survey with starting agents
        self.initial_results, self.initial_comparisons = self.starting_agents.take_survey(
            self.survey,
            gold_dictionary=self.gold_standard,
            comparison_factory=self.comparison_factory
        )
        
        if verbose:
            display_columns = self._get_display_columns(self.initial_results)
            self.console.print("\n[green]Initial Agent Responses:[/green]")
            print(self.initial_results.select(*display_columns).table())
            
            self.console.print("\n[green]Initial Performance Scores:[/green]")
            self.initial_comparisons.show_summary()
        
        self.logger.info(f"Initial evaluation completed: {len(self.starting_agents.agents)} agents evaluated")
        
        return self.initial_results, self.initial_comparisons
    
    def identify_optimization_targets(
        self, 
        selection_strategy: SelectionStrategy = "pareto",
        metric: Optional[str] = None,
        percentage: Optional[float] = None,
        count: Optional[int] = None,
        question: Optional[str] = None,
        verbose: bool = True
    ) -> CandidateAgentList:
        """Identify which agents to optimize using various selection strategies.
        
        Parameters
        ----------
        selection_strategy : SelectionStrategy, default "pareto"
            Strategy for selecting agents to optimize:
            - "all": Select all agents for optimization
            - "pareto": Select Pareto-optimal agents (non-dominated solutions)
            - "top_percent": Select top percentage of agents based on a metric
            - "top_count": Select top N agents based on a metric
        metric : str, optional
            Metric name for ranking agents (required for "top_percent" and "top_count").
            Examples: "exact_match", "overlap", "squared_distance", "cosine_similarity"
        percentage : float, optional
            Percentage of top agents to select (0-100, required for "top_percent")
        count : int, optional
            Number of top agents to select (required for "top_count")
        question : str, optional
            Specific question to evaluate metrics on. If None, uses aggregated metrics
        verbose : bool, default True
            If True, display detailed output
            
        Returns
        -------
        CandidateAgentList
            Agents selected for optimization
            
        Examples
        --------
        >>> # Select all agents
        >>> targets = optimizer.identify_optimization_targets(selection_strategy="all")
        
        >>> # Select Pareto-optimal agents
        >>> targets = optimizer.identify_optimization_targets(selection_strategy="pareto")
        
        >>> # Select top 20% based on exact match score
        >>> targets = optimizer.identify_optimization_targets(
        ...     selection_strategy="top_percent", 
        ...     metric="exact_match", 
        ...     percentage=20
        ... )
        
        >>> # Select top 5 agents based on overlap score
        >>> targets = optimizer.identify_optimization_targets(
        ...     selection_strategy="top_count", 
        ...     metric="overlap", 
        ...     count=5
        ... )
        """
        if verbose:
            self.console.print(f"\n[bold blue]IDENTIFYING OPTIMIZATION TARGETS[/bold blue]")
            self.console.print("="*60)
        
        # Validate parameters based on selection strategy
        if selection_strategy in ["top_percent", "top_count"] and metric is None:
            raise ValueError(f"Selection strategy '{selection_strategy}' requires 'metric' parameter")
        
        if selection_strategy == "top_percent" and percentage is None:
            raise ValueError("Selection strategy 'top_percent' requires 'percentage' parameter")
            
        if selection_strategy == "top_count" and count is None:
            raise ValueError("Selection strategy 'top_count' requires 'count' parameter")
        
        if selection_strategy == "all":
            # Select all agents for optimization
            targets = self.starting_agents
            if verbose:
                self.console.print(f"Selected ALL {len(targets.agents)} agents for optimization")
        else:
            # Use extract_top_agents for other strategies
            targets = self.initial_comparisons.extract_top_agents(
                method=selection_strategy,
                metric=metric,
                percentage=percentage,
                count=count,
                question=question
            )
            if verbose:
                strategy_desc = self._get_strategy_description(selection_strategy, metric, percentage, count, question)
                self.console.print(f"Selected {len(targets.agents)} agents using {strategy_desc}")
                targets.show()
        
        self.logger.info(f"Selected {len(targets.agents)} agents for optimization using strategy: {selection_strategy}")
        
        return targets
    
    def _get_strategy_description(self, strategy: str, metric: Optional[str], 
                                percentage: Optional[float], count: Optional[int], 
                                question: Optional[str]) -> str:
        """Generate a human-readable description of the selection strategy."""
        if strategy == "pareto":
            return "Pareto frontier (non-dominated solutions)"
        elif strategy == "top_percent":
            desc = f"top {percentage}% by {metric}"
            if question:
                desc += f" on question '{question}'"
            return desc
        elif strategy == "top_count":
            desc = f"top {count} agents by {metric}"
            if question:
                desc += f" on question '{question}'"
            return desc
        else:
            return f"'{strategy}' strategy"
    
    @log_method_calls
    def _handle_user_confirmation(self, target_agents: CandidateAgentList, verbose: bool) -> CandidateAgentList:
        """Handle user confirmation and agent count selection.
        
        Parameters
        ----------
        target_agents : CandidateAgentList
            Initial list of target agents
        verbose : bool
            Whether to display verbose output
            
        Returns
        -------
        CandidateAgentList
            Potentially limited list of agents based on user choice
        """
        self.console.print(f"\nThis will analyze and improve up to {len(target_agents.agents)} agents.")
        self.console.print("Each agent improvement involves multiple LLM calls and may take some time.")
        
        while True:
            try:
                user_input = input(f"How many agents would you like to optimize? (0-{len(target_agents.agents)}): ").strip()
                num_agents = int(user_input)
                
                if 0 <= num_agents <= len(target_agents.agents):
                    break
                else:
                    self.console.print(f"[red]Please enter a number between 0 and {len(target_agents.agents)}[/red]")
            except ValueError:
                self.console.print("[red]Please enter a valid number[/red]")
        
        if num_agents == 0:
            self.console.print("Skipping agent optimization.")
            return CandidateAgentList([], [])
        
        # Limit the target agents to the requested number
        if num_agents < len(target_agents.agents):
            limited_agents = target_agents.agents[:num_agents]
            limited_info = target_agents.info[:num_agents] if target_agents.info else [f"Agent {i+1}" for i in range(num_agents)]
            limited_target_agents = CandidateAgentList(limited_agents, limited_info)
            if verbose:
                self.console.print(f"[green]Will optimize the first {num_agents} agents[/green]")
            return limited_target_agents
        else:
            if verbose:
                self.console.print(f"[green]Will optimize all {num_agents} agents[/green]")
            return target_agents
    
    @log_method_calls
    def _setup_prompt_adjuster(self) -> 'PromptAdjust':
        """Set up and return a PromptAdjust instance for agent optimization.
        
        Returns
        -------
        PromptAdjust
            Configured PromptAdjust instance
        """
        return PromptAdjust(
            agent_results=self.initial_results,
            gold_standard_dict=self.gold_standard,
            survey=self.survey
        )
    
    @log_method_calls
    def _analyze_agent_performance(self, agent_name: str, adjuster: 'PromptAdjust', verbose: bool) -> dict:
        """Analyze agent performance and generate improvement suggestions.
        
        Parameters
        ----------
        agent_name : str
            Name of the agent to analyze
        adjuster : PromptAdjust
            PromptAdjust instance for analysis
        verbose : bool
            Whether to display verbose output
            
        Returns
        -------
        dict
            Analysis results containing improved persona and conflicts
        """
        improved_personas_dict = adjuster.generate_improved_personas([agent_name])
        
        if agent_name in improved_personas_dict:
            improved_data = improved_personas_dict[agent_name]
            improved_persona = improved_data.get("improved_persona", "")
            conflicts = improved_data.get("conflicts", "")
            
            if verbose:
                self.console.print(f"\n[cyan]Analysis for {agent_name}:[/cyan]")
                gap_analysis = adjuster.analyze_agent_gap(agent_name)
                self.console.print(f"  Performance gap: {gap_analysis[:200]}...")
                if conflicts:
                    self.console.print(f"  Conflicts: {conflicts}")
            
            return {
                'improved_persona': improved_persona,
                'conflicts': conflicts,
                'gap_analysis': adjuster.analyze_agent_gap(agent_name)
            }
        else:
            return {'improved_persona': '', 'conflicts': '', 'gap_analysis': ''}
    
    @log_method_calls
    def _apply_persona_improvement(self, agent: CandidateAgent, improved_persona: str, 
                                 agent_name: str, verbose: bool) -> list:
        """Apply persona improvement to an agent and return improved variants.
        
        Parameters
        ----------
        agent : CandidateAgent
            Original agent to improve
        improved_persona : str
            Improved persona suggestion
        agent_name : str
            Name of the agent
        verbose : bool
            Whether to display verbose output
            
        Returns
        -------
        list
            List of improved CandidateAgent objects
        """
        if verbose:
            self.console.print(f"\n[green]Improved persona:[/green] {improved_persona}")
            self.console.print(f"\n[magenta]Creating improved variant of {agent_name}...[/magenta]")
        
        original_list = CandidateAgentList([agent], [f"Original {agent_name}"])
        improved_list = original_list.apply_instructions([improved_persona])
        
        if verbose:
            self.console.print(f"Applied comprehensive improvement to {agent_name}")
            improved_list.show()
        
        if not improved_list.agents:
            if verbose:
                self.console.print(f"[yellow]Warning: No improved agents generated for {agent_name}[/yellow]")
            return []
        
        return improved_list.agents
    
    @log_method_calls
    def _optimize_single_agent(self, agent: CandidateAgent, agent_index: int, 
                              total_agents: int, adjuster: 'PromptAdjust', 
                              verbose: bool) -> list:
        """Optimize a single agent and return improved variants.
        
        Parameters
        ----------
        agent : CandidateAgent
            Agent to optimize
        agent_index : int
            Index of current agent (0-based)
        total_agents : int
            Total number of agents being optimized
        adjuster : PromptAdjust
            PromptAdjust instance for optimization
        verbose : bool
            Whether to display verbose output
            
        Returns
        -------
        list
            List of improved CandidateAgent objects
        """
        agent_name = agent.name
        
        if verbose:
            self.console.print(f"\n[yellow]--- Optimizing Agent {agent_index+1}/{total_agents}: {agent_name} ---[/yellow]")
        
        # Analyze agent performance
        analysis_results = self._analyze_agent_performance(agent_name, adjuster, verbose)
        improved_persona = analysis_results['improved_persona']
        
        # Apply improvement if persona suggestion exists
        if improved_persona and improved_persona.strip():
            improved_agents = self._apply_persona_improvement(agent, improved_persona, agent_name, verbose)
            
            if improved_agents:
                # Log the improvement
                self.optimization_log.append({
                    'agent_name': agent_name,
                    'gap_analysis': analysis_results['gap_analysis'],
                    'improved_persona_suggestion': improved_persona,
                    'improved_persona': improved_agents[0].persona if improved_agents else None
                })
                
                if verbose:
                    self.console.print(f"[green]Successfully optimized {agent_name}[/green]")
                
                return improved_agents
            else:
                return []
        else:
            if verbose:
                self.console.print(f"\n[green]{agent_name} is already performing optimally![/green]")
            return []
    
    @log_method_calls
    def _create_optimized_agents_list(self, optimized_agents: list, verbose: bool) -> CandidateAgentList:
        """Create the final CandidateAgentList from optimized agents.
        
        Parameters
        ----------
        optimized_agents : list
            List of optimized CandidateAgent objects
        verbose : bool
            Whether to display verbose output
            
        Returns
        -------
        CandidateAgentList
            Final list of optimized agents
        """
        if optimized_agents:
            try:
                optimized_list = CandidateAgentList(
                    optimized_agents, 
                    [f"optimized_{i+1}" for i in range(len(optimized_agents))]
                )
                if verbose:
                    self.console.print(f"\n[bold green]Optimization phase completed: {len(optimized_agents)} agents optimized[/bold green]")
                return optimized_list
            except Exception as e:
                if verbose:
                    self.console.print(f"[red]❌ CandidateAgentList creation failed: {e}[/red]")
                return CandidateAgentList([], [])
        else:
            if verbose:
                self.console.print(f"\n[bold yellow]Optimization phase completed: No agents were optimized[/bold yellow]")
            return CandidateAgentList([], [])
    
    @log_method_calls
    def optimize_agents(
        self, 
        target_agents: CandidateAgentList,
        max_suggestions_per_question: int = 2,
        verbose: bool = True,
        ask_confirmation: bool = False
    ) -> CandidateAgentList:
        """Optimize the target agents using LLM-driven improvements.
        
        This method orchestrates the agent optimization process by:
        1. Handling user confirmation if requested
        2. Setting up the PromptAdjust component
        3. Optimizing each agent individually
        4. Creating the final optimized agents list
        
        Parameters
        ----------
        target_agents : CandidateAgentList
            Agents to optimize
        max_suggestions_per_question : int, default 2
            Maximum suggestions per question (currently unused but kept for compatibility)
        verbose : bool, default True
            If True, display detailed output
        ask_confirmation : bool, default False
            If True, ask user for confirmation before proceeding
            
        Returns
        -------
        CandidateAgentList
            List of optimized agents
        """
        if verbose:
            self.console.print(f"\n[bold blue]AGENT OPTIMIZATION[/bold blue]")
            self.console.print("="*60)
        
        # Handle user confirmation if requested
        if ask_confirmation:
            target_agents = self._handle_user_confirmation(target_agents, verbose)
            if not target_agents.agents:  # User chose 0 agents
                return target_agents
        
        if verbose:
            self.console.print("Proceeding with agent improvements...")
        
        # Set up PromptAdjust component
        adjuster = self._setup_prompt_adjuster()
        
        # Optimize each agent
        optimized_agents = []
        for i, agent in enumerate(target_agents.agents):
            improved_variants = self._optimize_single_agent(
                agent, i, len(target_agents.agents), adjuster, verbose
            )
            optimized_agents.extend(improved_variants)
            
            if verbose and improved_variants:
                self.console.print(f"[green]Added {len(improved_variants)} improved agents. Total so far: {len(optimized_agents)}[/green]")
        
        # Create and store final optimized agents list
        self.optimized_agents = self._create_optimized_agents_list(optimized_agents, verbose)
        
        return self.optimized_agents
    
    def evaluate_final_performance(self, verbose: bool = True) -> tuple:
        """Evaluate final performance of optimized agents.
        
        Parameters
        ----------
        verbose
            If True, display detailed output
            
        Returns
        -------
        tuple
            (results, comparisons) from the final evaluation
        """
        if not self.optimized_agents or not self.optimized_agents.agents:
            if verbose:
                self.console.print("\n[yellow]No optimized agents to evaluate[/yellow]")
            return None, None
        
        if verbose:
            self.console.print(f"\n[bold blue]FINAL PERFORMANCE EVALUATION[/bold blue]")
            self.console.print("="*60)
        
        self.logger.info("Starting final performance evaluation")
        
        # Test all optimized agents
        self.final_results, self.final_comparisons = self.optimized_agents.take_survey(
            self.survey,
            gold_dictionary=self.gold_standard,
            comparison_factory=self.comparison_factory
        )
        
        if verbose:
            self.console.print(f"\nTesting all {len(self.optimized_agents.agents)} optimized agents...")
            
            # Display final responses
            final_display_columns = self._get_display_columns(self.final_results)
            self.console.print("\n[green]Final Performance Table:[/green]")
            print(self.final_results.select(*final_display_columns).table())
            
            # Display aggregated scores
            self.console.print("\n[green]Final Performance Scores (Aggregated):[/green]")
            self.final_comparisons.show_summary()
            
            # Enhanced performance table
            self._show_enhanced_performance_table()
            
            # Display by-question breakdown
            self.console.print("\n[green]Final Performance Scores (By Question):[/green]")
            self.final_comparisons.show()
        
        self.logger.info(f"Final evaluation completed: {len(self.optimized_agents.agents)} agents evaluated")
        
        return self.final_results, self.final_comparisons
    
    def _show_enhanced_performance_table(self):
        """Display enhanced performance table with perfect question percentages."""
        self.console.print("\n[bold green]Enhanced Performance Summary (with % Perfect Questions):[/bold green]")
        
        enhanced_table = Table(title="Final Agent Performance with Perfect Question Rate", show_lines=True)
        enhanced_table.add_column("Agent", style="bold magenta")
        enhanced_table.add_column("% Perfect Questions", style="green", justify="center")
        enhanced_table.add_column("Perfect Questions", style="cyan", justify="center")
        enhanced_table.add_column("Total Questions", style="cyan", justify="center")
        enhanced_table.add_column("Exact Match Score", style="yellow", justify="center")
        enhanced_table.add_column("Overlap Score", style="blue", justify="center")
        enhanced_table.add_column("New Persona", style="white")
        
        # Get the aggregated metrics for display
        aggregated_metrics = self.final_comparisons._aggregated_metrics()
        
        for idx, (comp, agg_metrics) in enumerate(zip(self.final_comparisons, aggregated_metrics)):
            # Calculate perfect questions count
            comp_dict = comp.compare()
            total_questions = len(comp_dict)
            perfect_questions = sum(1 for ac in comp_dict.values() if ac['exact_match'] == 1.0)
            perfect_fraction = perfect_questions / total_questions if total_questions > 0 else 0
            
            # Get agent identifier and new persona
            try:
                agent_data = comp.result_A["agent"]
                agent_name = agent_data.traits.get("agent_name", f"agent_{idx}")
                new_persona = agent_data.traits.get("persona", "Unknown persona")
            except:
                agent_name = f"agent_{idx}"
                new_persona = "Unknown persona"
            
            # Truncate persona for display
            max_persona_len = 80
            display_persona = new_persona if len(new_persona) <= max_persona_len else new_persona[:max_persona_len-3] + "..."
            
            # Get scores
            exact_match = agg_metrics.get('exact_match', 0)
            overlap = agg_metrics.get('overlap', 0)
            
            enhanced_table.add_row(
                f"{idx + 1}. {agent_name}",
                f"{perfect_fraction:.1%}",
                str(perfect_questions),
                str(total_questions),
                f"{exact_match:.3f}" if exact_match == exact_match else "-",  # Check for NaN
                f"{overlap:.3f}" if overlap == overlap else "-",  # Check for NaN
                display_persona
            )
        
        self.console.print(enhanced_table)
    
    def optimize(
        self,
        selection_strategy: SelectionStrategy = "pareto",
        metric: Optional[str] = None,
        percentage: Optional[float] = None,
        count: Optional[int] = None,
        question: Optional[str] = None,
        max_suggestions_per_question: int = 2,
        verbose: bool = True,
        ask_confirmation: bool = False
    ) -> OptimizationResults:
        """Run the complete optimization process.
        
        Parameters
        ----------
        selection_strategy : SelectionStrategy, default "pareto"
            Strategy for selecting agents to optimize:
            - "all": Select all agents for optimization
            - "pareto": Select Pareto-optimal agents (non-dominated solutions)
            - "top_percent": Select top percentage of agents based on a metric
            - "top_count": Select top N agents based on a metric
        metric : str, optional
            Metric name for ranking agents (required for "top_percent" and "top_count")
        percentage : float, optional
            Percentage of top agents to select (0-100, required for "top_percent")
        count : int, optional
            Number of top agents to select (required for "top_count")
        question : str, optional
            Specific question to evaluate metrics on. If None, uses aggregated metrics
        max_suggestions_per_question : int, default 2
            Maximum suggestions per question for improvements
        verbose : bool, default True
            If True, display detailed output throughout the process
        ask_confirmation : bool, default False
            If True, ask user for confirmation before starting optimization
            
        Returns
        -------
        OptimizationResults
            Comprehensive results object with convenient access methods including:
            - Direct access to optimized agents: results.optimized_agents
            - Convert to EDSL AgentList: results.to_edsl_agent_list()
            - Get optimization details: results.optimization_log
            - Print summary: results.print_summary()
            
        Examples
        --------
        Basic usage:
        
        >>> optimizer = AgentOptimizer(survey, gold_standard, starting_agents)
        >>> results = optimizer.optimize()
        >>> results.print_summary()
        
        Access optimized agents:
        
        >>> # As CandidateAgent objects
        >>> for agent in results.optimized_agents.agents:
        ...     print(f"Agent: {agent.name}")
        ...     print(f"New persona: {agent.persona}")
        
        >>> # As EDSL AgentList (recommended for further surveys)
        >>> edsl_agents = results.to_edsl_agent_list()
        >>> new_survey = Survey([QuestionYesNo("Are you confident?", "confident")])
        >>> edsl_results = new_survey.by(edsl_agents).run()
        
        >>> # Get optimization details
        >>> for detail in results.get_improvement_details():
        ...     print(f"Agent: {detail['agent_name']}")
        ...     print(f"Questions improved: {list(detail['suggestions_per_question'].keys())}")
        ...     print(f"Comprehensive suggestion: {detail['comprehensive_suggestion']}")
        """
        self.logger.info("="*60)
        self.logger.info("STARTING AGENT OPTIMIZATION PROCESS")
        self.logger.info("="*60)
        
        if verbose:
            self.console.print("\n[bold cyan]🚀 AGENT OPTIMIZATION FRAMEWORK[/bold cyan]")
            self.console.print("="*60)
            self.console.print(f"Survey: {len(self.survey.questions)} questions")
            self.console.print(f"Starting agents: {len(self.starting_agents.agents)}")
            self.console.print(f"Gold standard: {list(self.gold_standard.keys())}")
        
        try:
            # Step 1: Evaluate initial performance
            self.evaluate_initial_performance(verbose=verbose)
            
            # Step 2: Identify optimization targets
            target_agents = self.identify_optimization_targets(
                selection_strategy=selection_strategy,
                metric=metric,
                percentage=percentage,
                count=count,
                question=question,
                verbose=verbose
            )
            
            # Step 3: Optimize agents
            optimized_agents = self.optimize_agents(
                target_agents=target_agents,
                max_suggestions_per_question=max_suggestions_per_question,
                verbose=verbose,
                ask_confirmation=ask_confirmation
            )
            
            # Step 4: Evaluate final performance
            self.evaluate_final_performance(verbose=verbose)
            
            # Compile results
            results = {
                'initial_results': self.initial_results,
                'initial_comparisons': self.initial_comparisons,
                'target_agents': target_agents,
                'optimized_agents': self.optimized_agents,
                'final_results': self.final_results,
                'final_comparisons': self.final_comparisons,
                'optimization_log': self.optimization_log,
                'optimized_agents_summary': self.get_optimized_agents_summary(),
                'summary': self._generate_summary()
            }
            
            if verbose:
                self.console.print(f"\n[bold green]✅ OPTIMIZATION COMPLETE![/bold green]")
                self.console.print("="*60)
                summary = results['summary']
                self.console.print(f"• Initial agents: {summary['initial_agent_count']}")
                self.console.print(f"• Optimized agents: {summary['optimized_agent_count']}")
                self.console.print(f"• Improvement rate: {summary['improvement_rate']:.1%}")
                if summary['average_perfect_questions'] is not None:
                    self.console.print(f"• Average perfect questions: {summary['average_perfect_questions']:.1%}")
            
            self.logger.info("Optimization process completed successfully")
            return OptimizationResults(results)
            
        except Exception as e:
            self.logger.error(f"Optimization process failed: {e}")
            if verbose:
                self.console.print(f"\n[bold red]❌ OPTIMIZATION FAILED: {e}[/bold red]")
            raise
    
    def get_optimized_agents_summary(self) -> dict:
        """Get a summary of optimized agents with their new prompts.
        
        Returns
        -------
        dict
            Dictionary containing optimized agent information with keys:
            - 'agents': list of optimized CandidateAgent objects
            - 'agent_details': list of dicts with name, original_persona, new_persona
            - 'count': number of optimized agents
        """
        if not self.optimized_agents or not self.optimized_agents.agents:
            return {
                'agents': [],
                'agent_details': [],
                'count': 0
            }
        
        # Create detailed agent information
        agent_details = []
        for i, agent in enumerate(self.optimized_agents.agents):
            # Try to find the original persona from optimization log
            original_persona = None
            if i < len(self.optimization_log):
                log_entry = self.optimization_log[i]
                # Get original persona from starting agents if available
                for orig_agent in self.starting_agents.agents:
                    if orig_agent.name == log_entry['agent_name']:
                        original_persona = orig_agent.persona
                        break
            
            agent_details.append({
                'name': agent.name,
                'original_persona': original_persona or "Unknown",
                'new_persona': agent.persona,
                'optimization_log': self.optimization_log[i] if i < len(self.optimization_log) else None
            })
        
        return {
            'agents': self.optimized_agents.agents,
            'agent_details': agent_details,
            'count': len(self.optimized_agents.agents)
        }
    
    def get_performance_analytics(self):
        """Generate comprehensive performance analytics for the optimization process.
        
        Returns
        -------
        dict
            Detailed analytics including improvement metrics, convergence analysis,
            optimization effectiveness, and comparative statistics.
        """
        analytics = {
            'optimization_overview': self._get_optimization_overview(),
            'performance_improvement': self._analyze_performance_improvement(),
            'convergence_analysis': self._analyze_convergence(),
            'question_difficulty_analysis': self._analyze_question_difficulty(),
            'agent_diversity_analysis': self._analyze_agent_diversity(),
            'optimization_efficiency': self._analyze_optimization_efficiency(),
            'statistical_significance': self._test_statistical_significance()
        }
        
        return analytics
        
    def _get_optimization_overview(self):
        """Basic overview of the optimization run."""
        return {
            'total_starting_agents': len(self.starting_agents.agents),
            'agents_selected_for_optimization': len(self.optimization_log),
            'successfully_optimized_agents': len(self.optimized_agents.agents) if self.optimized_agents else 0,
            'optimization_success_rate': len(self.optimized_agents.agents) / len(self.optimization_log) if self.optimization_log else 0,
            'total_questions': len(self.survey.questions),
            'gold_standard_coverage': len(self.gold_standard) / len(self.survey.questions)
        }
        
    def _analyze_performance_improvement(self):
        """Analyze performance improvements before/after optimization."""
        if not (self.initial_comparisons and self.final_comparisons):
            return {'error': 'Missing initial or final comparisons'}
            
        # Get metric improvements for agents that were optimized
        improvements = {
            'per_agent_improvements': [],
            'aggregate_improvements': {},
            'improvement_distribution': {}
        }
        
        # Map optimized agents back to their originals
        optimized_names = [log['agent_name'] for log in self.optimization_log]
        
        initial_aggregated = self.initial_comparisons._aggregated_metrics()
        final_aggregated = self.final_comparisons._aggregated_metrics()
        
        if not initial_aggregated or not final_aggregated:
            return improvements
            
        # Calculate per-agent improvements
        for i, log_entry in enumerate(self.optimization_log):
            agent_name = log_entry['agent_name']
            
            # Find original agent index
            original_idx = None
            for j, comp in enumerate(self.initial_comparisons):
                try:
                    if comp.result_A["agent"].get("agent_name") == agent_name:
                        original_idx = j
                        break
                except:
                    continue
                    
            if original_idx is not None and i < len(final_aggregated):
                initial_metrics = initial_aggregated[original_idx]
                final_metrics = final_aggregated[i]
                
                agent_improvement = {
                    'agent_name': agent_name,
                    'metric_improvements': {},
                    'overall_improvement': 0
                }
                
                total_improvement = 0
                valid_metrics = 0
                
                for metric in initial_metrics:
                    initial_val = initial_metrics[metric]
                    final_val = final_metrics.get(metric, initial_val)
                    
                    if isinstance(initial_val, (int, float)) and isinstance(final_val, (int, float)):
                        if not (initial_val != initial_val or final_val != final_val):  # Filter NaN
                            improvement = final_val - initial_val
                            percent_change = (improvement / initial_val * 100) if initial_val != 0 else 0
                            
                            agent_improvement['metric_improvements'][metric] = {
                                'initial': initial_val,
                                'final': final_val,
                                'absolute_improvement': improvement,
                                'percent_improvement': percent_change
                            }
                            
                            total_improvement += improvement
                            valid_metrics += 1
                            
                if valid_metrics > 0:
                    agent_improvement['overall_improvement'] = total_improvement / valid_metrics
                    
                improvements['per_agent_improvements'].append(agent_improvement)
                
        # Calculate aggregate improvements across all metrics
        if improvements['per_agent_improvements']:
            metric_names = set()
            for agent_imp in improvements['per_agent_improvements']:
                metric_names.update(agent_imp['metric_improvements'].keys())
                
            for metric in metric_names:
                metric_improvements = []
                for agent_imp in improvements['per_agent_improvements']:
                    if metric in agent_imp['metric_improvements']:
                        metric_improvements.append(agent_imp['metric_improvements'][metric]['absolute_improvement'])
                        
                if metric_improvements:
                    improvements['aggregate_improvements'][metric] = {
                        'mean_improvement': sum(metric_improvements) / len(metric_improvements),
                        'median_improvement': sorted(metric_improvements)[len(metric_improvements)//2],
                        'min_improvement': min(metric_improvements),
                        'max_improvement': max(metric_improvements),
                        'std_improvement': (sum((x - sum(metric_improvements)/len(metric_improvements))**2 for x in metric_improvements) / len(metric_improvements)) ** 0.5,
                        'agents_improved': sum(1 for x in metric_improvements if x > 0),
                        'agents_degraded': sum(1 for x in metric_improvements if x < 0)
                    }
                    
        return improvements
        
    def _analyze_convergence(self):
        """Analyze convergence properties of the optimization."""
        if not self.final_comparisons:
            return {'error': 'No final comparisons available'}
            
        # Analyze distribution of final scores
        final_aggregated = self.final_comparisons._aggregated_metrics()
        if not final_aggregated:
            return {'error': 'No aggregated metrics available'}
            
        convergence = {
            'pareto_frontier_size': len(self.final_comparisons.nondominated()),
            'pareto_percentage': len(self.final_comparisons.nondominated()) / len(final_aggregated) * 100,
            'metric_convergence': {},
            'overall_score_distribution': {}
        }
        
        # Analyze convergence for each metric
        metric_names = list(final_aggregated[0].keys())
        
        for metric in metric_names:
            values = [agg[metric] for agg in final_aggregated if isinstance(agg[metric], (int, float)) and not (agg[metric] != agg[metric])]
            
            if values:
                mean_val = sum(values) / len(values)
                variance = sum((x - mean_val)**2 for x in values) / len(values)
                
                convergence['metric_convergence'][metric] = {
                    'mean': mean_val,
                    'variance': variance,
                    'coefficient_of_variation': (variance ** 0.5) / mean_val if mean_val != 0 else float('inf'),
                    'range': max(values) - min(values),
                    'agents_at_maximum': sum(1 for x in values if x == max(values))
                }
                
        return convergence
        
    def _analyze_question_difficulty(self):
        """Analyze which questions were most/least difficult to optimize."""
        if not (self.initial_comparisons and self.final_comparisons):
            return {'error': 'Missing comparison data'}
            
        question_analysis = {}
        
        # Get per-question performance for initial and final states
        for question in [q.question_name for q in self.survey.questions]:
            initial_scores = []
            final_scores = []
            
            # Initial scores
            for comp in self.initial_comparisons:
                comp_dict = comp.compare()
                if question in comp_dict:
                    initial_scores.append(comp_dict[question]['exact_match'])
                    
            # Final scores (only for optimized agents)
            for comp in self.final_comparisons:
                comp_dict = comp.compare()
                if question in comp_dict:
                    final_scores.append(comp_dict[question]['exact_match'])
                    
            if initial_scores and final_scores:
                initial_mean = sum(initial_scores) / len(initial_scores)
                final_mean = sum(final_scores) / len(final_scores)
                
                question_analysis[question] = {
                    'initial_accuracy': initial_mean,
                    'final_accuracy': final_mean,
                    'accuracy_improvement': final_mean - initial_mean,
                    'initial_sample_size': len(initial_scores),
                    'final_sample_size': len(final_scores),
                    'difficulty_rank': 1 - initial_mean,  # Higher rank = more difficult initially
                    'optimization_effectiveness': (final_mean - initial_mean) / (1 - initial_mean) if initial_mean < 1 else 0
                }
                
        return question_analysis
        
    def _analyze_agent_diversity(self):
        """Analyze diversity characteristics of the agent population."""
        diversity = {
            'initial_diversity': {},
            'final_diversity': {},
            'diversity_change': {}
        }
        
        # Initial diversity
        if self.initial_comparisons:
            initial_aggregated = self.initial_comparisons._aggregated_metrics()
            if initial_aggregated:
                diversity['initial_diversity'] = self._calculate_population_diversity(initial_aggregated)
                
        # Final diversity
        if self.final_comparisons:
            final_aggregated = self.final_comparisons._aggregated_metrics()
            if final_aggregated:
                diversity['final_diversity'] = self._calculate_population_diversity(final_aggregated)
                
        # Calculate diversity change
        if diversity['initial_diversity'] and diversity['final_diversity']:
            for metric in diversity['initial_diversity']:
                if metric in diversity['final_diversity']:
                    initial_var = diversity['initial_diversity'][metric]['variance']
                    final_var = diversity['final_diversity'][metric]['variance']
                    
                    diversity['diversity_change'][metric] = {
                        'variance_change': final_var - initial_var,
                        'variance_change_percent': ((final_var - initial_var) / initial_var * 100) if initial_var > 0 else 0
                    }
                    
        return diversity
        
    def _calculate_population_diversity(self, aggregated_metrics):
        """Calculate diversity metrics for a population."""
        diversity = {}
        
        if not aggregated_metrics:
            return diversity
            
        metric_names = list(aggregated_metrics[0].keys())
        
        for metric in metric_names:
            values = [agg[metric] for agg in aggregated_metrics if isinstance(agg[metric], (int, float)) and not (agg[metric] != agg[metric])]
            
            if len(values) > 1:
                mean_val = sum(values) / len(values)
                variance = sum((x - mean_val)**2 for x in values) / len(values)
                
                diversity[metric] = {
                    'mean': mean_val,
                    'variance': variance,
                    'std': variance ** 0.5,
                    'range': max(values) - min(values),
                    'unique_values': len(set(values))
                }
                
        return diversity
        
    def _analyze_optimization_efficiency(self):
        """Analyze the efficiency of the optimization process."""
        efficiency = {
            'suggestions_per_agent': {},
            'optimization_patterns': {},
            'time_analysis': {},
            'success_patterns': {}
        }
        
        if self.optimization_log:
            # Analyze suggestions per agent
            total_suggestions = 0
            agent_suggestion_counts = []
            
            for log_entry in self.optimization_log:
                suggestions_per_q = log_entry.get('suggestions_per_question', {})
                agent_total = sum(len(suggestions) if isinstance(suggestions, list) else 1 
                                for suggestions in suggestions_per_q.values())
                agent_suggestion_counts.append(agent_total)
                total_suggestions += agent_total
                
            if agent_suggestion_counts:
                efficiency['suggestions_per_agent'] = {
                    'mean': sum(agent_suggestion_counts) / len(agent_suggestion_counts),
                    'median': sorted(agent_suggestion_counts)[len(agent_suggestion_counts)//2],
                    'min': min(agent_suggestion_counts),
                    'max': max(agent_suggestion_counts),
                    'total': total_suggestions
                }
                
            # Identify common optimization patterns
            all_suggestions = []
            for log_entry in self.optimization_log:
                comprehensive = log_entry.get('comprehensive_suggestion', '')
                if comprehensive:
                    all_suggestions.append(comprehensive.lower())
                    
            if all_suggestions:
                # Simple keyword frequency analysis
                from collections import Counter
                import re
                
                # Extract common words from suggestions
                all_text = ' '.join(all_suggestions)
                words = re.findall(r'\b\w+\b', all_text)
                
                # Filter out common words
                stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 
                           'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 
                           'will', 'would', 'could', 'should', 'may', 'might', 'must', 'this', 'that', 'these', 'those',
                           'more', 'make', 'add', 'include', 'persona'}
                
                filtered_words = [w for w in words if len(w) > 3 and w not in stopwords]
                word_counts = Counter(filtered_words)
                
                efficiency['optimization_patterns'] = {
                    'most_common_themes': dict(word_counts.most_common(10)),
                    'total_unique_words': len(set(filtered_words)),
                    'vocabulary_diversity': len(set(filtered_words)) / len(filtered_words) if filtered_words else 0
                }
                
        return efficiency
        
    def _test_statistical_significance(self):
        """Test statistical significance of improvements."""
        if not (self.initial_comparisons and self.final_comparisons):
            return {'error': 'Missing comparison data'}
            
        # This is a simplified statistical test
        # In practice, you might want to use proper statistical tests like t-tests
        
        significance = {
            'metric_significance_tests': {},
            'effect_sizes': {},
            'confidence_intervals': {}
        }
        
        # Get paired data for agents that were optimized
        optimized_names = [log['agent_name'] for log in self.optimization_log]
        
        initial_aggregated = self.initial_comparisons._aggregated_metrics()
        final_aggregated = self.final_comparisons._aggregated_metrics()
        
        if not (initial_aggregated and final_aggregated):
            return significance
            
        metric_names = list(initial_aggregated[0].keys())
        
        for metric in metric_names:
            initial_values = []
            final_values = []
            
            # Match agents between initial and final
            for i, log_entry in enumerate(self.optimization_log):
                agent_name = log_entry['agent_name']
                
                # Find original agent
                original_idx = None
                for j, comp in enumerate(self.initial_comparisons):
                    try:
                        if comp.result_A["agent"].get("agent_name") == agent_name:
                            original_idx = j
                            break
                    except:
                        continue
                        
                if original_idx is not None and i < len(final_aggregated):
                    initial_val = initial_aggregated[original_idx].get(metric)
                    final_val = final_aggregated[i].get(metric)
                    
                    if (isinstance(initial_val, (int, float)) and isinstance(final_val, (int, float)) and 
                        not (initial_val != initial_val or final_val != final_val)):
                        initial_values.append(initial_val)
                        final_values.append(final_val)
                        
            if len(initial_values) >= 2:  # Need at least 2 pairs for meaningful statistics
                differences = [f - i for f, i in zip(final_values, initial_values)]
                mean_diff = sum(differences) / len(differences)
                
                if len(differences) > 1:
                    var_diff = sum((d - mean_diff)**2 for d in differences) / (len(differences) - 1)
                    std_diff = var_diff ** 0.5
                    
                    # Simple t-statistic (assumes normal distribution)
                    t_stat = mean_diff / (std_diff / (len(differences) ** 0.5)) if std_diff > 0 else 0
                    
                    # Effect size (Cohen's d)
                    pooled_std = ((sum((i - sum(initial_values)/len(initial_values))**2 for i in initial_values) + 
                                  sum((f - sum(final_values)/len(final_values))**2 for f in final_values)) / 
                                 (len(initial_values) + len(final_values) - 2)) ** 0.5
                    
                    cohens_d = mean_diff / pooled_std if pooled_std > 0 else 0
                    
                    significance['metric_significance_tests'][metric] = {
                        'sample_size': len(differences),
                        'mean_improvement': mean_diff,
                        'std_improvement': std_diff,
                        't_statistic': t_stat,
                        'degrees_of_freedom': len(differences) - 1
                    }
                    
                    significance['effect_sizes'][metric] = {
                        'cohens_d': cohens_d,
                        'interpretation': self._interpret_cohens_d(cohens_d)
                    }
                    
        return significance
        
    def _interpret_cohens_d(self, d):
        """Interpret Cohen's d effect size."""
        abs_d = abs(d)
        if abs_d < 0.2:
            return 'negligible'
        elif abs_d < 0.5:
            return 'small'
        elif abs_d < 0.8:
            return 'medium'
        else:
            return 'large'
            
    def export_analytics_report(self, filename: str = None):
        """Export comprehensive analytics to a structured report.
        
        Parameters
        ----------
        filename : str, optional
            Output filename. If None, returns report as dictionary.
            
        Returns
        -------
        dict or None
            Report dictionary if filename is None, otherwise writes to file
        """
        analytics = self.get_performance_analytics()
        
        # Create comprehensive report
        report = {
            'metadata': {
                'optimization_timestamp': self._get_timestamp(),
                'survey_questions': [q.question_name for q in self.survey.questions],
                'gold_standard': self.gold_standard,
                'starting_agent_count': len(self.starting_agents.agents),
                'optimization_method': 'documented_in_log',
                'metrics_used': [str(fn) for fn in self.comparison_factory.comparison_fns]
            },
            'analytics': analytics,
            'detailed_logs': self.optimization_log
        }
        
        if filename:
            import json
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, default=str)
            return None
        else:
            return report
            
    def _get_timestamp(self):
        """Get current timestamp string."""
        import datetime
        return datetime.datetime.now().isoformat()
    
    def _generate_summary(self) -> dict:
        """Generate summary statistics of the optimization process."""
        summary = {
            'initial_agent_count': len(self.starting_agents.agents),
            'optimized_agent_count': len(self.optimized_agents.agents) if self.optimized_agents else 0,
            'improvement_rate': None,
            'average_perfect_questions': None,
            'optimization_log_count': len(self.optimization_log)
        }
        
        if summary['initial_agent_count'] > 0:
            summary['improvement_rate'] = summary['optimized_agent_count'] / summary['initial_agent_count']
        
        # Calculate average perfect question rate if final comparisons exist
        if self.final_comparisons:
            total_perfect_rate = 0
            count = 0
            
            for comp in self.final_comparisons:
                comp_dict = comp.compare()
                total_questions = len(comp_dict)
                perfect_questions = sum(1 for ac in comp_dict.values() if ac['exact_match'] == 1.0)
                if total_questions > 0:
                    total_perfect_rate += perfect_questions / total_questions
                    count += 1
            
            if count > 0:
                summary['average_perfect_questions'] = total_perfect_rate / count
        
        return summary


__all__ = ["AgentOptimizer", "OptimizationResults", "SelectionStrategy"] 