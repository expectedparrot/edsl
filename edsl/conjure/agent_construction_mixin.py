import random
import sys
from typing import Generator, List, Optional, Union, Callable
from edsl.agents import Agent
from edsl.agents import AgentList
from edsl.questions import QuestionBase
from edsl.results import Results
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.table import Table
from rich.panel import Panel
import traceback
import psutil
import gc


class AgentConstructionModule:
    def __init__(self, input_data):
        self.input_data = input_data
    
    def agent(self, index) -> Agent:
        """Return an agent constructed from the data.

        :param index: The index of the agent to construct.

        >>> from .input_data import InputDataABC
        >>> id = InputDataABC.example()
        >>> id.agent_construction.agent(0)
        Agent(traits = {'morning': '1', 'feeling': '3'}, codebook = {'morning': 'how are you doing this morning?', 'feeling': 'how are you feeling?'})


        """
        responses = [responses[index] for responses in self.input_data.raw_data]
        traits = {f"{qn}_agent": r for qn, r in zip(self.input_data.question_names, responses)}

        adjusted_codebook = {k + "_agent": v for k, v in self.input_data.names_to_texts.items()}

        # Create a custom traits presentation template
        template_lines = [
            "{% for key, value in traits.items() %}",
            "When you were asked: {{ codebook[key] if codebook and key in codebook else key.replace('_agent', '') }}",
            "{% if value is iterable and value is not string %}",
            "    {% for v in value %}",
            "You responded: {{ v }}",
            "    {% endfor %}",
            "{% else %}",
            "You responded: {{ value }}",
            "{% endif %}",
            "",
            "{% endfor %}",
        ]
        traits_presentation_template = "\n".join(template_lines)

        a = Agent(traits=traits, codebook=adjusted_codebook, traits_presentation_template=traits_presentation_template)

        def construct_answer_dict_function(traits: dict) -> Callable:
            def func(self, question: "QuestionBase", scenario=None):
                return traits.get(question.question_name + "_agent", None)

            return func

        a.add_direct_question_answering_method(construct_answer_dict_function(traits))
        return a

    def _agents(self, indices) -> Generator[Agent, None, None]:
        """Return a generator of agents, one for each index."""
        for idx in indices:
            yield self.agent(idx)

    def to_agent_list(
        self,
        indices: Optional[List] = None,
        sample_size: int = None,
        seed: str = "edsl",
        remove_direct_question_answering_method: bool = True,
    ) -> AgentList:
        """Return an AgentList from the data.

        :param indices: The indices of the agents to include.
        :param sample_size: The number of agents to sample.
        :param seed: The seed for the random number generator.

        >>> from .input_data import InputDataABC
        >>> id = InputDataABC.example()
        >>> al = id.agent_construction.to_agent_list()
        >>> len(al) == id.num_observations
        True
        >>> al = id.agent_construction.to_agent_list(indices = [0, 1, 2])
        Traceback (most recent call last):
        ...
        ValueError: Index 2 is greater than the number of agents 2.
        """
        if indices and (sample_size or seed != "edsl"):
            raise ValueError(
                "You cannot pass both indices and sample_size/seed, as these are mutually exclusive."
            )

        if indices:
            if len(indices) == 0:
                raise ValueError("Indices must be a non-empty list.")
            if max(indices) >= self.input_data.num_observations:
                raise ValueError(
                    f"Index {max(indices)} is greater than the number of agents {self.input_data.num_observations}."
                )
            if min(indices) < 0:
                raise ValueError(f"Index {min(indices)} is less than 0.")

        if indices is None:
            if sample_size is None:
                indices = range(self.input_data.num_observations)
            else:
                if sample_size > self.input_data.num_observations:
                    raise ValueError(
                        f"Sample size {sample_size} is greater than the number of agents {self.input_data.num_observations}."
                    )
                random.seed(seed)
                indices = random.sample(range(self.input_data.num_observations), sample_size)

        agents = list(self._agents(indices))
        if remove_direct_question_answering_method:
            for a in agents:
                a.remove_direct_question_answering_method()
        return AgentList(agents)

    def to_results(
        self,
        indices: Optional[List] = None,
        sample_size: int = None,
        seed: str = "edsl",
        dryrun=False,
        disable_remote_cache: bool = False,
        disable_remote_inference: bool = True,
        verbose: bool = False,
    ) -> Union[Results, None]:
        """Return the results of the survey.

        :param indices: The indices of the agents to include.
        :param sample_size: The number of agents to sample.
        :param seed: The seed for the random number generator.
        :param dryrun: If True, the survey will not be run, but the time to run it will be printed.
        :param verbose: If True, display detailed progress information to stderr.

        >>> from .input_data import InputDataABC
        >>> id = InputDataABC.example()
        >>> r = id.agent_construction.to_results(disable_remote_cache = True, disable_remote_inference = True)
        >>> len(r) == id.num_observations
        True
        """
        console = Console(stderr=True)
        
        if verbose:
            console.print("[bold blue]Starting survey conversion process...[/bold blue]")
            
            # System diagnostics
            try:
                process = psutil.Process()
                memory_info = process.memory_info()
                console.print(f"[dim]💾 Initial memory usage: {memory_info.rss / 1024 / 1024:.1f} MB[/dim]")
                console.print(f"[dim]🖥️  CPU count: {psutil.cpu_count()}, Load: {psutil.getloadavg()[0]:.2f}[/dim]" if hasattr(psutil, 'getloadavg') else f"[dim]🖥️  CPU count: {psutil.cpu_count()}[/dim]")
            except Exception:
                pass  # Ignore if psutil diagnostics fail
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeRemainingColumn(),
                console=console,
                disable=not verbose
            ) as progress:
            
                # Step 1: Create agent list
                total_agents = sample_size if sample_size else (len(indices) if indices else self.input_data.num_observations)
                agent_task = progress.add_task("[cyan]Creating agent list...", total=total_agents)
                
                if verbose:
                    console.print(f"[dim]Processing {total_agents} agents from {self.input_data.num_observations} total observations in {self.input_data.datafile_name}[/dim]")
                    if sample_size:
                        console.print(f"[dim]Using random sample of {sample_size} agents with seed '{seed}'[/dim]")
                    elif indices:
                        console.print(f"[dim]Using specified indices: {len(indices)} agents[/dim]")
                
                try:
                    agent_list = self.to_agent_list(
                        indices=indices,
                        sample_size=sample_size,
                        seed=seed,
                        remove_direct_question_answering_method=False,
                    )
                    progress.update(agent_task, completed=total_agents)
                    
                    if verbose:
                        console.print(f"[green]✓[/green] Created {len(agent_list)} agents successfully")
                        
                except Exception as e:
                    console.print(f"[red]❌ Failed to create agent list: {e}[/red]")
                    if verbose:
                        console.print(f"[red]Traceback:[/red]")
                        console.print(traceback.format_exc())
                    raise
            
                # Step 2: Create survey
                num_questions = len(self.input_data.question_names)
                survey_task = progress.add_task("[cyan]Creating survey...", total=num_questions)
                if verbose:
                    console.print(f"[dim]Converting {num_questions} questions to EDSL survey format[/dim]")
                
                try:
                    # Create a progress callback to update the main progress bar
                    def survey_progress_callback(completed):
                        progress.update(survey_task, completed=completed)
                    
                    survey = self.input_data.to_survey(verbose=verbose, progress_callback=survey_progress_callback if verbose else None)
                    progress.update(survey_task, completed=num_questions)
                    
                    if verbose:
                        valid_questions = len([q for q in survey.questions if q is not None])
                        console.print(f"[green]✓[/green] Created survey with {valid_questions} valid questions")
                        
                        # Memory check after survey creation
                        try:
                            process = psutil.Process()
                            memory_info = process.memory_info()
                            console.print(f"[dim]💾 Memory after survey creation: {memory_info.rss / 1024 / 1024:.1f} MB[/dim]")
                        except Exception:
                            pass
                            
                except Exception as e:
                    console.print(f"[red]❌ Failed to create survey: {e}[/red]")
                    if verbose:
                        console.print(f"[red]Traceback:[/red]")
                        console.print(traceback.format_exc())
                    raise
            
                # Step 3: Handle dryrun
                if dryrun:
                    import time
                    
                    DRYRUN_SAMPLE = min(30, len(agent_list))  # Don't sample more than we have
                    dryrun_task = progress.add_task(f"[yellow]Running dryrun ({DRYRUN_SAMPLE} agents)...", total=DRYRUN_SAMPLE)
                    
                    if verbose:
                        console.print(f"[dim]Running performance test with {DRYRUN_SAMPLE} agents to estimate timing[/dim]")

                    try:
                        start = time.time()
                        dryrun_results = survey.by(agent_list.sample(DRYRUN_SAMPLE)).run(
                            disable_remote_cache=disable_remote_cache,
                            disable_remote_inference=disable_remote_inference,
                        )
                        end = time.time()
                        
                        progress.update(dryrun_task, completed=DRYRUN_SAMPLE)
                        
                        elapsed_time = end - start
                        time_per_agent = elapsed_time / DRYRUN_SAMPLE
                        full_sample_time = time_per_agent * len(agent_list)
                        
                        console.print(f"[green]✓[/green] Dryrun completed: {DRYRUN_SAMPLE} agents in {elapsed_time:.2f}s ({time_per_agent:.2f}s per agent)")
                        
                        if verbose and dryrun_results:
                            console.print(f"[dim]Dryrun produced {len(dryrun_results)} result records[/dim]")
                        
                        # Enhanced time estimates with better formatting
                        if full_sample_time < 60:
                            console.print(f"[bold yellow]📊 Estimated time for all {len(agent_list)} agents: {full_sample_time:.1f} seconds[/bold yellow]")
                        elif full_sample_time < 3600:
                            console.print(f"[bold yellow]📊 Estimated time for all {len(agent_list)} agents: {full_sample_time / 60:.1f} minutes[/bold yellow]")
                        else:
                            console.print(f"[bold yellow]📊 Estimated time for all {len(agent_list)} agents: {full_sample_time / 3600:.1f} hours[/bold yellow]")
                        
                        console.print(f"[dim]Use --sample to reduce the number of agents if this seems too long[/dim]")
                        return None
                        
                    except Exception as e:
                        console.print(f"[red]❌ Dryrun failed: {e}[/red]")
                        if verbose:
                            console.print(f"[red]Traceback:[/red]")
                            console.print(traceback.format_exc())
                        raise
            
                # Step 4: Run the actual survey
                run_task = progress.add_task(f"[green]Running survey ({len(agent_list)} agents)...", total=len(agent_list))
                
                # Additional diagnostics before running survey
                if verbose:
                    console.print(f"[dim]🔧 Survey configuration:[/dim]")
                    console.print(f"[dim]   • Questions: {len(survey.questions)}[/dim]")
                    console.print(f"[dim]   • Agents: {len(agent_list)}[/dim]")
                    console.print(f"[dim]   • Disable remote cache: {disable_remote_cache}[/dim]")
                    console.print(f"[dim]   • Disable remote inference: {disable_remote_inference}[/dim]")
                
                # If we have more than 10 agents and verbose is enabled, do a timing estimate
                if len(agent_list) > 10 and verbose:
                    import time
                    
                    console.print(f"[dim]Running timing sample with first 10 agents out of {len(agent_list)}[/dim]")
                    
                    # Time the first 10 agents
                    start_time = time.time()
                    sample_results = survey.by(agent_list[:10]).run(
                        disable_remote_cache=disable_remote_cache,
                        disable_remote_inference=disable_remote_inference,
                    )
                    end_time = time.time()
                    
                    # Calculate timing estimates
                    sample_time = end_time - start_time
                    time_per_agent = sample_time / 10
                    estimated_total_time = time_per_agent * len(agent_list)
                    
                    # Update progress for completed sample
                    progress.update(run_task, completed=10)
                    
                    console.print(f"[green]✓[/green] Sample of 10 agents completed in {sample_time:.2f}s")
                    console.print(f"[dim]Performance: {time_per_agent:.2f}s per agent[/dim]")
                    
                    if estimated_total_time < 60:
                        console.print(f"[yellow]🕒 Estimated total time: {estimated_total_time:.1f} seconds[/yellow]")
                    elif estimated_total_time < 3600:
                        console.print(f"[yellow]🕒 Estimated total time: {estimated_total_time / 60:.1f} minutes[/yellow]")
                    else:
                        console.print(f"[yellow]🕒 Estimated total time: {estimated_total_time / 3600:.1f} hours[/yellow]")
                    
                    # Calculate estimated time for remaining agents
                    remaining_agents = len(agent_list) - 10
                    estimated_remaining_time = time_per_agent * remaining_agents
                    
                    if estimated_remaining_time < 60:
                        time_display = f"{estimated_remaining_time:.1f} seconds"
                    elif estimated_remaining_time < 3600:
                        time_display = f"{estimated_remaining_time / 60:.1f} minutes"
                    else:
                        time_display = f"{estimated_remaining_time / 3600:.1f} hours"
                    
                    console.print(f"[dim]Now running full survey with remaining {remaining_agents} agents (estimated time: {time_display})[/dim]")
                    
                    # Start full survey timer
                    full_survey_start = time.time()
                    
                    # Run the remaining agents
                    remaining_results = survey.by(agent_list[10:]).run(
                        disable_remote_cache=disable_remote_cache,
                        disable_remote_inference=disable_remote_inference,
                    )
                    
                    # Calculate total elapsed time and throughput
                    total_elapsed = time.time() - full_survey_start + sample_time
                    throughput = len(agent_list) / total_elapsed if total_elapsed > 0 else 0
                    
                    if total_elapsed < 60:
                        console.print(f"[green]✓[/green] Total elapsed time: {total_elapsed:.1f} seconds")
                    elif total_elapsed < 3600:
                        console.print(f"[green]✓[/green] Total elapsed time: {total_elapsed / 60:.1f} minutes")
                    else:
                        console.print(f"[green]✓[/green] Total elapsed time: {total_elapsed / 3600:.1f} hours")
                    
                    console.print(f"[blue]📊 Throughput: {throughput:.1f} agents/second[/blue]")
                    
                    # Update progress for completed agents
                    progress.update(run_task, completed=len(agent_list))
                    
                    # Combine results
                    results = sample_results + remaining_results
                
                else:
                    if verbose:
                        console.print(f"[dim]Running survey with {len(agent_list)} agents[/dim]")
                    
                    # Start timer for full survey
                    import time
                    survey_start = time.time()
                    
                    results = survey.by(agent_list).run(
                        disable_remote_cache=disable_remote_cache,
                        disable_remote_inference=disable_remote_inference,
                    )
                
                    # Update progress and calculate elapsed time and throughput
                    progress.update(run_task, completed=len(agent_list))
                    elapsed = time.time() - survey_start
                    throughput = len(agent_list) / elapsed if elapsed > 0 else 0
                    
                    if verbose:
                        if elapsed < 60:
                            console.print(f"[green]✓[/green] Total elapsed time: {elapsed:.1f} seconds")
                        elif elapsed < 3600:
                            console.print(f"[green]✓[/green] Total elapsed time: {elapsed / 60:.1f} minutes")
                        else:
                            console.print(f"[green]✓[/green] Total elapsed time: {elapsed / 3600:.1f} hours")
                        
                        console.print(f"[blue]📊 Throughput: {throughput:.1f} agents/second[/blue]")
            
                if verbose:
                    console.print("[bold green]✓ Survey conversion completed successfully![/bold green]")
                    console.print(f"[dim]Final results contain {len(results)} agent responses[/dim]")
                    
                    # Final memory check
                    try:
                        process = psutil.Process()
                        memory_info = process.memory_info()
                        console.print(f"[dim]💾 Final memory usage: {memory_info.rss / 1024 / 1024:.1f} MB[/dim]")
                    except Exception:
                        pass
                
                return results
                
        except KeyboardInterrupt:
            console.print("[yellow]⚠ Process interrupted by user[/yellow]")
            raise
        except Exception as e:
            console.print(f"[red]❌ Fatal error in survey conversion: {e}[/red]")
            if verbose:
                console.print(f"[red]Full traceback:[/red]")
                console.print(traceback.format_exc())
                
                # Emergency memory cleanup
                try:
                    gc.collect()
                    console.print("[dim]🧹 Performed garbage collection[/dim]")
                except Exception:
                    pass
            raise


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
