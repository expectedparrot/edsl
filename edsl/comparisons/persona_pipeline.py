from __future__ import annotations

"""Pipeline to transform a *Result* into a persona-based agent, rerun a survey and
compare the new answers with the original ones.

The main entry point is :class:`PersonaPipeline`.  Typical usage::

    pipeline = PersonaPipeline(result, survey)
    # Run the whole workflow in one call
    comparison = pipeline.run()
    comparison.print_table()

If you need more control you can call the individual steps::

    pipeline.generate_persona()        # step 1–3
    pipeline.create_persona_agent()    # step 4
    new_results = pipeline.run_survey() # step 5
    comparison = pipeline.compare_results() # step 6

You can remove traits explicitly::

    pipeline = PersonaPipeline(result, survey, traits_to_remove=["age", "hobbies"])

…or ask the class to randomly drop *n* traits before generating the persona::

    pipeline = PersonaPipeline(result, survey, num_traits_to_remove=2)
"""

from typing import Any, Optional

from edsl import Agent, AgentList, QuestionFreeText
from edsl.utilities import local_results_cache

from rich.console import Console

from .result_pair_comparison import ResultPairComparison
from .factory import ComparisonFactory

from dataclasses import dataclass, field

__all__ = ["PersonaPipeline"]

# ------------------------------------------------------------------
# Default personality survey used in examples/tests
# ------------------------------------------------------------------

from edsl import (
    QuestionYesNo,
    QuestionList,
    QuestionNumerical,
    QuestionMultipleChoice,
    QuestionCheckBox,
)

personality_survey = (
    QuestionFreeText(
        question_name="hobbies",
        question_text="What are your main hobbies and interests?",
    )
    .add_question(
        QuestionYesNo(
            question_name="social_media_user",
            question_text="Do you actively use social media platforms?",
        )
    )
    .add_question(
        QuestionList(
            question_name="favorite_genres",
            question_text="What are your favorite entertainment genres (books, movies, music)?",
        )
    )
    .add_question(
        QuestionNumerical(
            question_name="age",
            question_text="What is your age?",
        )
    )
    .add_question(
        QuestionMultipleChoice(
            question_name="education_level",
            question_text="What is your highest level of education?",
            question_options=[
                "High school diploma",
                "Bachelor's degree",
                "Master's degree",
                "PhD or higher",
                "Trade school/certification",
                "No formal education",
            ],
        )
    )
    .add_question(
        QuestionCheckBox(
            question_name="personality_traits",
            question_text="Which personality traits describe you best?",
            question_options=[
                "Extroverted",
                "Introverted",
                "Creative",
                "Analytical",
                "Adventurous",
                "Cautious",
                "Optimistic",
                "Pragmatic",
            ],
        )
    )
)


@dataclass
class CandidateAgent:
    """Container holding all artefacts related to a single candidate persona."""

    seed_agent: Agent  # Agent after trait removal
    traits_removed: list[str] = field(default_factory=list)
    info: str | None = None

    # Will be populated later in the pipeline ---------------------------------
    persona_text: str | None = None
    persona_agent: Agent | None = None
    results: Any | None = None
    comparison: ResultPairComparison | None = None

    # Convenience helpers ------------------------------------------------------
    @property
    def kept_traits(self) -> dict:
        return self.seed_agent.traits

    def __repr__(self):
        return (
            f"CandidateAgent(kept={list(self.seed_agent.traits)}, "
            f"removed={self.traits_removed})"
        )


class CandidateAgentList(list):
    """Light wrapper around a list of CandidateAgent objects with helpers."""

    def seed_agents(self) -> AgentList:
        from edsl import AgentList  # local import to avoid circular

        return AgentList([c.seed_agent for c in self])

    def persona_agents(self):
        return AgentList([c.persona_agent for c in self if c.persona_agent is not None])

    def traits_matrix(self):
        return [c.seed_agent.traits for c in self]

    # ------------------------------------------------------------------
    # Factory helper
    # ------------------------------------------------------------------

    @classmethod
    def build(
        cls,
        base_agent: Agent,
        n_agents: int,
        generator: callable,
        rng: "random.Random",
        info_list: Optional[list[str]] = None,
    ) -> "CandidateAgentList":
        """Construct a list of `CandidateAgent` objects using *generator*.

        Parameters
        ----------
        base_agent
            The unmodified agent derived from the original result.
        n_agents
            How many candidate variants to create.
        generator
            Callable implementing the candidate-creation strategy.
        rng
            Random number generator instance used by the generator.
        info_list
            Optional list of info strings to associate with each candidate.
        """

        c_list = cls()
        for idx in range(n_agents):
            seed, removed = generator(base_agent, rng, idx)
            info_value = None
            if info_list and idx < len(info_list):
                info_value = info_list[idx]
            else:
                # fallback: use instruction of seed agent if set
                info_value = getattr(seed, "instruction", None)
            c_list.append(
                CandidateAgent(
                    seed_agent=seed,
                    traits_removed=list(removed),
                    info=info_value,
                )
            )
        return c_list

    # ------------------------------------------------------------------
    # Vectorised persona generation
    # ------------------------------------------------------------------

    def generate_personas(self, persona_question: Any):
        """Run *one* job to obtain persona texts for all seed agents.

        The method populates ``candidate.persona_text`` for every entry and
        returns the collected list of texts.
        """

        from edsl import AgentList  # local import to avoid circular
        from edsl.utilities import local_results_cache

        seed_list: AgentList = AgentList([c.seed_agent for c in self])

        persona_job = persona_question.by(seed_list)  # type: ignore[attr-defined]
        with local_results_cache(persona_job) as results:
            texts: list[str] = results.select("persona").to_list()  # type: ignore[attr-defined]

        # Map texts back to candidates in order
        for cand, txt in zip(self, texts):
            cand.persona_text = txt

        return texts

    # ------------------------------------------------------------------
    # Persona Agent creation
    # ------------------------------------------------------------------

    def create_persona_agents(self):
        """Instantiate `Agent` objects with the generated persona texts."""

        from edsl import Agent, AgentList  # local import

        agents = []
        for cand in self:
            if cand.persona_text is None:
                raise RuntimeError("Persona texts have not been generated yet.")
            cand.persona_agent = Agent(traits={"persona": cand.persona_text})
            agents.append(cand.persona_agent)

        return AgentList(agents)

    # ------------------------------------------------------------------
    # Display helper
    # ------------------------------------------------------------------

    def show(self, console: Optional[Console] = None):
        """Render a rich table with info and persona text for each candidate."""

        if console is None:
            console = Console()

        from rich.table import Table

        table = Table(title="Candidates Overview")
        table.add_column("#", justify="right")
        table.add_column("Info", overflow="fold")
        table.add_column("Persona (first 80 chars)", overflow="fold")

        for idx, cand in enumerate(self, start=1):
            persona_preview = (cand.persona_text or "<not generated>")[:80]
            table.add_row(str(idx), cand.info or "-", persona_preview)

        console.print(table)
        return table


class PersonaPipeline:
    """End-to-end helper to derive a persona from an existing *Result* and compare.

    Parameters
    ----------
    original_result
        An individual :class:`edsl.Results` entry – usually obtained by iterating
        over an ``edsl.Results`` container.
    survey
        A *Job* (built using the fluent ``Question...`` interface) to be executed
        by the newly created persona agent.
    num_traits_to_remove
        Alternatively, provide an **integer** to randomly sample that many
        traits for removal.  If both *traits_to_remove* and
        *num_traits_to_remove* are supplied, the explicit list takes
        precedence and random sampling is skipped.
    persona_question
        Custom *Question* used to elicit the persona.  By default a single
        ``QuestionFreeText`` requesting a two-paragraph description is used.
    comparison_factory
        Allows customising the metrics used during comparison.  Defaults to the
        standard :class:`ComparisonFactory`.
    candidate_generator
        Optional callable to generate candidate agents.
    verbose
        If *True*, the pipeline prints informative progress messages using
        *rich*; you can also pass an explicit :class:`rich.console.Console*
        instance via the *console* parameter.
    console
        Optional :class:`rich.console.Console* to use for logging; if *verbose*
        is *True* and *console* is *None* a new console will be created.
    n_agents
        Number of persona variants to generate.
    random_seed
        Seed for random number generation.
    """

    def __init__(
        self,
        original_result: Any,
        survey: Any,
        *,
        num_traits_to_remove: int | None = None,
        persona_question: Optional[Any] = None,
        comparison_factory: Optional[ComparisonFactory] = None,
        candidate_generator: Optional[callable] = None,
        verbose: bool = False,
        console: Console | None = None,
        n_agents: int = 1,
        random_seed: int | None = None,
    ) -> None:
        self.original_result = original_result
        self.survey = survey
        self.num_traits_to_remove = num_traits_to_remove
        self.n_agents = max(1, n_agents)

        # ------------------------------------------------------------------
        # Logging / console setup
        # ------------------------------------------------------------------

        self.verbose = verbose
        self.console: Console | None = console if verbose else None
        if self.verbose and self.console is None:
            self.console = Console()

        def _log(msg: str):
            if self.console:
                self.console.print(msg)

        self._log = _log  # save as instance method for convenience

        # ------------------------------------------------------------------
        # Step 1 – build agent from the provided *Result*
        # ------------------------------------------------------------------
        self.base_agent: Agent = Agent.from_result(original_result)

        self._log(
            "[bold]Original traits:[/bold] "
            + ", ".join(map(str, self.base_agent.traits.keys()))
        )

        # ------------------------------------------------------------------
        # Step 2 – create *candidate* agents that will each be turned into a
        # unique persona later on.  These variants are stored in
        # `self.candidate_agents` and are the foundation for all subsequent
        # steps.
        # ------------------------------------------------------------------

        import random as _random_module

        self._rng = _random_module.Random(random_seed)

        # ---------------- Candidate generator ------------------------------
        def _default_generator(base: Agent, rng: _random_module.Random, idx: int):
            trait_pool = list(base.traits.keys())
            k = self.num_traits_to_remove or 0
            removed = rng.sample(trait_pool, k=min(k, len(trait_pool))) if k > 0 else []
            new_agent = base
            for t in removed:
                new_agent = new_agent.remove_trait(t)
            return new_agent, removed

        self.candidate_generator = candidate_generator or _default_generator

        # Build CandidateAgentList via factory
        info_list = [self.base_agent.instruction] * self.n_agents
        self.candidates = CandidateAgentList.build(
            base_agent=self.base_agent,
            n_agents=self.n_agents,
            generator=self.candidate_generator,
            rng=self._rng,
            info_list=info_list,
        )

        # Convenience AgentList for vectorised jobs
        self.seed_agent_list: AgentList = self.candidates.seed_agents()

        # Question to elicit persona – can be overridden by the caller
        self.persona_question = persona_question or QuestionFreeText(
            question_name="persona",
            question_text="Please give a 2 paragraph description of yourself.",
        )

        # Comparison metrics
        self.comparison_factory = comparison_factory or ComparisonFactory()

        # Runtime artefacts – filled as the pipeline progresses
        self.persona_text: Optional[str] = None  # text for *first* candidate
        # Data structures for (potentially) multiple persona variants
        self.persona_texts: list[str] = []
        self.persona_agents: Optional[AgentList] = None
        self.new_results_list: list[Any] = []
        self._comparisons: Optional[list[ResultPairComparison]] = None

    # ------------------------------------------------------------------
    # Pipeline steps (public so users can call them individually)
    # ------------------------------------------------------------------

    def generate_persona(self) -> None:
        """Populate persona texts for all candidates using the helper on the list."""

        if self.persona_texts:
            return

        collected_texts = self.candidates.generate_personas(self.persona_question)

        self.persona_texts = collected_texts

        self._log("[green]Generated persona texts:[/green]")
        for i, txt in enumerate(collected_texts, start=1):
            self._log(f"Persona {i}: {txt[:80]}{'...' if len(txt) > 80 else ''}")

    def run_survey(self) -> Any:
        """Execute the survey with all persona agents.

        Returns
        -------
        Any | list[Any]
            * A single `Results` object if `n_agents == 1`.
            * A list of `Results` (one per agent) otherwise.
        """

        if self.persona_agents is None:
            self.persona_agents = self.candidates.create_persona_agents()

        # ------------------------------------------------------------------
        # Vectorised survey – one job for all persona agents.
        # ------------------------------------------------------------------

        survey_job = self.survey.by(self.persona_agents)  # type: ignore[attr-defined]
        with local_results_cache(survey_job) as results_container:
            # `results_container` will typically be a Results object with one
            # entry per agent in the same order as `self.persona_agents`.
            new_results_collected = list(results_container)

        # Persist ------------------------------------------------------------
        self.new_results_list = new_results_collected
        if new_results_collected:
            self.new_results = new_results_collected[0]

        self._log(
            "[bold]Survey completed – obtained new results for all persona agents.[/bold]"
        )

        return new_results_collected[0] if self.n_agents == 1 else new_results_collected

    def compare_results(self) -> ResultPairComparison | list[ResultPairComparison]:
        """Create comparison objects between the original result and each new result."""

        if not self.new_results_list:
            self.run_survey()

        comparisons: list[ResultPairComparison] = []

        for new_res in self.new_results_list:
            comp = ResultPairComparison(
                self.original_result, new_res, self.comparison_factory
            )
            comparisons.append(comp)

        # Persist ----------------------------------------------------------------
        self._comparisons = comparisons

        self._log("[bold]Results comparison objects ready.[/bold]")

        return comparisons[0] if self.n_agents == 1 else comparisons

    def score_matrix(
        self,
        *,
        metric_weights: Optional[dict[str, float]] = None,
        include_original: bool = False,
    ) -> list[list[float | None]]:
        """Compute an *upper-triangular* matrix of weighted scores between agents.

        Parameters
        ----------
        metric_weights
            Mapping of *metric_name* -> *weight* passed to
            :meth:`ResultPairComparison.weighted_score`.  If *None*, a default
            weighing is used where the *exact_match* metric and *all* cosine
            similarity metrics receive a weight of ``1.0`` and **all other
            metrics are set to ``0.0``.
        include_original
            If *True*, the *original* results entry is inserted as the first
            row/column of the matrix so that similarities between the
            seed-agent and each persona are also reported.

        Returns
        -------
        list[list[float | None]]
            A square ``n × n`` matrix (encoded as nested lists) where
            ``n`` is the number of considered agents.  The matrix is filled
            *only* for the upper triangle (``i < j``); the lower triangle and
            diagonal contain ``None`` as placeholders.
        """

        # Ensure we have fresh results available --------------------------------
        if not self.new_results_list:
            # Trigger the full pipeline up to result generation if needed
            self.generate_persona()
            self.persona_agents = self.candidates.create_persona_agents()
            self.run_survey()

        # Assemble the list of *Results* objects to compare ----------------------
        results_to_consider = list(self.new_results_list)
        if include_original:
            results_to_consider.insert(0, self.original_result)

        n = len(results_to_consider)
        matrix: list[list[float | None]] = [[None] * n for _ in range(n)]

        # ------------------------------------------------------------------
        # Default metric weights – focus on *exact_match* and any cosine sims
        # ------------------------------------------------------------------
        if metric_weights is None:
            metric_names = [str(fn) for fn in self.comparison_factory.comparison_fns]
            metric_weights = {
                name: (
                    1.0
                    if (name == "exact_match" or name.startswith("cosine_similarity"))
                    else 0.0
                )
                for name in metric_names
            }

        # ------------------------------------------------------------------
        # Compute pair-wise scores (upper triangle only)
        # ------------------------------------------------------------------
        for i in range(n):
            for j in range(i + 1, n):
                comp = ResultPairComparison(
                    results_to_consider[i],
                    results_to_consider[j],
                    comparison_factory=self.comparison_factory,
                )
                score = comp.weighted_score(metric_weights=metric_weights)
                matrix[i][j] = score

        return matrix

    # Convenience helper to pretty-print the matrix -----------------------------
    def print_score_matrix(
        self,
        *,
        metric_weights: Optional[dict[str, float]] = None,
        include_original: bool = False,
        console: Console | None = None,
    ) -> None:
        """Render the score matrix via a *rich* table."""

        from rich.table import Table

        if console is None:
            console = self.console or Console()

        matrix = self.score_matrix(
            metric_weights=metric_weights, include_original=include_original
        )
        n = len(matrix)

        # Build header ----------------------------------------------------
        table = Table(title="Agent Score Matrix (upper-triangle)")
        table.add_column("i\\j", justify="right")
        for j in range(n):
            table.add_column(str(j))

        for i, row in enumerate(matrix):
            display_row: list[str] = [str(i)]
            for j in range(n):
                val = row[j]
                if val is None:
                    display_row.append("-")
                else:
                    display_row.append(f"{val:.3f}")
            table.add_row(*display_row)

        console.print(table)
        return table

    # ------------------------------------------------------------------
    # Convenience one-shot runner
    # ------------------------------------------------------------------

    def run(self) -> ResultPairComparison | list[ResultPairComparison]:
        """Execute *all* stages of the pipeline.

        This is a thin convenience wrapper that sequentially triggers persona
        generation, agent creation, survey execution and result comparison.

        Returns
        -------
        ResultPairComparison | list[ResultPairComparison]
            Matches the behaviour of other public methods:
            • A single `ResultPairComparison` instance when `n_agents == 1`.
            • A list of `ResultPairComparison` objects (one per persona) otherwise.
        """

        if self._comparisons is None:
            self.generate_persona()
            self.persona_agents = self.candidates.create_persona_agents()
            self._log(
                f"[bold]Created {len(self.persona_agents)} persona agent(s).[/bold]"
            )
            self.run_survey()
            self.compare_results()

        return self._comparisons[0] if self.n_agents == 1 else self._comparisons


# --------------------------------------------------------------------------------------
# Minimal demonstration – executed when the module is run as a script
# --------------------------------------------------------------------------------------

if __name__ == "__main__":
    """Run a quick demo: build a tiny survey, derive three personas and print comparisons."""

    console = Console()

    # Run the personality_survey once with a generic agent to obtain an original result
    # ------------------------------------------------------------------

    seed_agent = Agent(
        traits={
            "persona": "I am a 25 year old male who likes to play video games and watch movies."
        }
    )
    survey_job = personality_survey.by(seed_agent)  # type: ignore[attr-defined]

    with local_results_cache(survey_job) as results:
        original_result = results[0]

    # ------------------------------------------------------------------
    # Execute the PersonaPipeline with multiple variants
    # ------------------------------------------------------------------

    pipeline = PersonaPipeline(
        original_result,
        personality_survey,
        num_traits_to_remove=3,
        n_agents=15,
        verbose=True,
        console=console,
        random_seed=42,
    )

    comparisons = pipeline.run()

    console.print("\n[bold]Generated Personas:[/bold]")
    for idx, txt in enumerate(pipeline.persona_texts, start=1):
        console.print(f"[{idx}] {txt}\n")

    console.print("[bold]Comparison Tables:[/bold]")
    for idx, (cand, agent, comp) in enumerate(
        zip(pipeline.candidates, pipeline.persona_agents, comparisons), start=1
    ):
        console.print(
            f"\n[underline]Candidate Agent {idx} Traits:[/underline] {cand.kept_traits}"
        )
        console.print(f"[italic]Persona Agent {idx}:[/italic] {agent}")
        comp.print_table(console)

    # --------------------------------------------------------------
    # Score matrix between persona agents
    # --------------------------------------------------------------

    console.print("\n[bold]Score Matrix:[/bold]")
    pipeline.print_score_matrix(console=console, include_original=True)
