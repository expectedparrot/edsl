from __future__ import annotations
import asyncio
import logging
import textwrap
from collections import UserList
from typing import Any, Type, List, Generator, Callable, List
from edsl import CONFIG
from edsl.agents import Agent
from edsl.exceptions import InterviewErrorPriorTaskCanceled, InterviewTimeoutError
from edsl.language_models import LanguageModel
from edsl.questions import Question
from edsl.scenarios import Scenario
from edsl.surveys import Survey
from edsl.utilities.decorators import sync_wrapper
from edsl.data_transfer_models import AgentResponseDict
from edsl.jobs.Answers import Answers

from edsl.surveys.base import EndOfSurvey

from edsl.jobs.buckets import ModelBuckets
from edsl.jobs.token_tracking import TokenUsage, InterviewTokenUsage

## Ideas: 
## https://github.com/openai/openai-cookbook/blob/main/examples/api_request_parallel_processor.py

class TasksList(UserList):

    def status(self, debug=False):
        if debug:
            for task in self:
                print(f"Task {task.edsl_name}")
                print(f"\t DEPENDS ON: {task.depends_on}")
                print(f"\t DONE: {task.done()}")
                print(f"\t CANCELLED: {task.cancelled()}")
                if not task.cancelled():
                    if task.done():
                        print(f"\t RESULT: {task.result()}")
                    else:
                        print(f"\t RESULT: None - Not done yet")  

            print("---------------------")

# create logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = False
# create  file handler
fh = logging.FileHandler(CONFIG.get("EDSL_LOGGING_PATH"))
fh.setLevel(logging.INFO)
# add formatter to the handlers
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(funcName)s - %(message)s"
)
fh.setFormatter(formatter)
# add handler to logger
logger.addHandler(fh)

# start loggin'
logger.info("Interview.py loaded")

TIMEOUT = float(CONFIG.get("API_CALL_TIMEOUT_SEC"))

class QuestionTaskCreator(UserList):
    """Class to create and manage question tasks with dependencies.
    It is a UserList with all the tasks that must be completed before the focal task can be run.
    When called, it returns an asyncio.Task that depends on the tasks that must be completed before it can be run.
    """

    def __init__(self, *, question: Question, func: Callable, model_buckets: ModelBuckets, token_estimator: Callable = None):
        super().__init__([])
        self.func = func
        self.question = question
        self.model_buckets = model_buckets
        self.waiting = False
        self.from_cache = False
        self.token_estimator = token_estimator

        self.cached_token_usage = TokenUsage(from_cache = True)
        self.new_token_usage = TokenUsage(from_cache = False)

    def add_dependency(self, task):
        """Adds a dependency to the list of dependencies."""
        self.append(task)

    def generate_task(self, debug) -> asyncio.Task:
        """Creates a task that depends on the passed-in dependencies."""
        task = asyncio.create_task(self._run_task_async(debug))
        task.edsl_name = self.question.question_name
        task.depends_on = [x.edsl_name for x in self] 
        return task
    
    def estimated_tokens(self) -> int:
        """Estimates the number of tokens that will be required to run the focal task."""
        # TODO: Um, actually compute this.
        token_estimate = self.token_estimator(self.question)
        #breakpoint()
        return token_estimate
    
    def token_usage(self) -> dict:
        """Returns the token usage for the task."""
        return {'cached_tokens': self.cached_token_usage, 'new_tokens': self.new_token_usage}

    async def _run_focal_task(self, debug) -> 'Answers':
        """Runs the focal task i.e., the question that we are interested in answering.
        It is only called after all the dependency tasks are completed. 
        """
        self.requests_bucket = self.model_buckets.requests_bucket
        self.tokens_bucket = self.model_buckets.tokens_bucket

        # TODO: This isn't quite right because while you are waiting for the 
        # requests token, the tokens bucket might get exhaused - though actually that's fine because
        # you already reserved them. 
        logger.info(f"Current bucket tokens balance: {self.tokens_bucket.tokens}")
        requested_tokens = self.estimated_tokens()
        logger.info(f"Requesting {requested_tokens} tokens for {self.question.question_name}") 
        if (estimated_wait_time := self.tokens_bucket.wait_time(requested_tokens)) > 0:
            #print("Pausing for TPM")
            logger.info(f"Estimated time until tokens are available: {estimated_wait_time}")
            self.waiting = True
        await self.tokens_bucket.get_tokens(requested_tokens)
        self.waiting = False
        logger.info("Token funds acquired!")


        ## Requests per minute check
        logger.info(f"Request bucket balance: {self.requests_bucket.tokens}")
        if (estimated_wait_time := self.requests_bucket.wait_time(1)) > 0:
            logger.info(f"Pausing {self.question.question_name} for {estimated_wait_time} seconds to stay under RPM limit")
            #print("Pausing for RPM")
            self.waiting = True
        await self.requests_bucket.get_tokens(1)
        self.waiting = False
        logger.info(f"Requests funds acquired!")

        results = await self.func(self.question, debug)

        # If the result was cached, we don't need to use any tokens
        if 'cached_response' in results:
            if results['cached_response']:
                logger.info(f"Result for {self.question.question_name} was cached.")
                # put the tokens back; didn't need them
                self.tokens_bucket.add_tokens(requested_tokens)
                self.requests_bucket.add_tokens(1)
                self.from_cache = 1

        # Track token usage
                
        tracker = self.cached_token_usage if self.from_cache else self.new_token_usage
        usage = results.get('usage', {'prompt_tokens': 0, 'completion_tokens': 0})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        tracker.add_tokens(prompt_tokens = prompt_tokens, completion_tokens = completion_tokens)

        return results

    async def _run_task_async(self, debug) -> 'Answers':
        """Runs the task asynchronously, awaiting the tasks that must be completed before this one can be run."""
        logger.info(f"Running task for {self.question.question_name}")
        try:
            # This is waiting for the tasks that must be completed before this one can be run.
            # This does *not* use the return_exceptions = True flag, so if any of the tasks fail,
            # it throws the exception immediately, which is what we want.
            await asyncio.gather(*self)
        except asyncio.CancelledError:
            logger.info(f"Task for {self.question.question_name} was cancelled, most likely because it was skipped.")
            raise
        except Exception as e:
            logger.error(f"Required tasks for {self.question.question_name} failed: {e}")
            # turns the parent exception into a custom exception
            # So the task gets canceled but this InterviewErrorPriorTaskCanceled exception
            # So we never get the question details we need.
            raise InterviewErrorPriorTaskCanceled(
                f"Required tasks failed for {self.question.question_name}"
            ) from e
        else:
            logger.info(f"Tasks for {self.question.question_name} completed")
            # This is the actual task that we want to run.
            #results = await self.func(question, debug)
            #return results
            return await self._run_focal_task(debug)


class Interview:
    """
    A class that has an Agent answer Survey Questions with a particular Scenario and using a LanguageModel.
    """

    def __init__(
        self,
        agent: Agent,
        survey: Survey,
        scenario: Scenario,
        model: Type[LanguageModel],
        verbose: bool = False,
        debug: bool = False,
    ):
        self.agent = agent
        self.survey = survey
        self.scenario = scenario
        self.model = model
        self.debug = debug
        self.verbose = verbose
        self.answers: dict[str, str] = Answers()  # will get filled in

        self.dag = self.survey.dag(
            textify=True
        )  # the DAG tells us what questions depend on what other questions
        self.to_index = {
            name: index for index, name in enumerate(self.survey.question_names)
        }
        # Make huge-ass bucket for testing purposes so it goes quickly
        # TODO: Check config if in testing mode and use giant bucket
        #self.bucket = bucket or TokenBucket(capacity=2000000000000,refill_rate=1000000000000)

        logger.info(f"Interview instantiated")
        self.task_creators = {}

    

    @property
    def token_usage(self) -> dict:
        cached_tokens = TokenUsage(from_cache = True)
        new_tokens = TokenUsage(from_cache = False)
        for task_creator in self.task_creators.values():
            token_usage = task_creator.token_usage()
            cached_tokens += token_usage["cached_tokens"]
            new_tokens += token_usage["new_tokens"]
        return InterviewTokenUsage(new_token_usage=new_tokens, cached_token_usage=cached_tokens)

    @property
    def num_tasks_waiting(self):
        return sum([task_creator.waiting for task_creator in self.task_creators.values()])
    
    @property
    def num_from_cache(self):
        return sum([task_creator.from_cache for task_creator in self.task_creators.values()])

    async def async_conduct_interview(
        self, 
        model_buckets: ModelBuckets, 
        debug: bool = False, replace_missing: bool = True
    ) -> tuple["Answers", List[dict[str, Any]]]:
        """
        Conducts an 'interview' asynchronously. An interview is:
        - one agent
        - one survey (so multiple questions)
        - one model
        - one scenario

        Args:
            debug (bool): Enable debugging mode.
            replace_missing (bool): Replace missing answers with None.
            threaded (bool): Flag to use threading if required.

        Returns:
            Tuple[Answers, List[Dict[str, Any]]]: The answers and a list of valid results.
        """

        self.tasks, self.invigilators = self._build_question_tasks(debug = debug, model_buckets = model_buckets)
        
        self.tasks.status()

        # when return_exceptions=False, it will just raise the exception
        # and break the loop; otherwise it returns.                
        
        #debug = True
        return_exceptions = not debug 
        
        await asyncio.gather(*self.tasks, return_exceptions=return_exceptions)
            
        if replace_missing:
            self.answers.replace_missing_answers_with_none(self.survey)

        valid_results = list(self._extract_valid_results(self.tasks, self.invigilators))

        logger.info(f"Total of tasks requested:\t {len(self.tasks)}")
        logger.info(f"Number of valid results:\t {len(valid_results)}")
        return self.answers, valid_results

    #conduct_interview = sync_wrapper(async_conduct_interview)

    def _extract_valid_results(self, tasks, invigialtors) -> Generator["Answers", None, None]:
        """Extracts the valid results from the list of results."""

        warning_header = textwrap.dedent(
            """\
            WARNING: At least one question in the survey was not answered.
            """
        )
        # there should be one one invigilator for each task
        assert len(self.tasks) == len(self.invigilators)
        warning_printed = False

        self.tasks.status()

        for task, invigilator in zip(self.tasks, self.invigilators):
            logger.info(f"Iterating through task: {task}")
            if task.done():
                try:
                    result = task.result()
                except asyncio.CancelledError:
                    logger.info(f"Task `{task.edsl_name}` was cancelled.")
                    result = invigilator.get_failed_task_result()
                except Exception as exception:
                    if not warning_printed:
                        warning_printed = True
                        print(warning_header)
                    
                    error_message = f"Task `{task.edsl_name}` failed with `{exception.__class__.__name__}`:`{exception}`."
                    logger.error(error_message)
                    print(error_message)
                    # if task failed, we use the invigilator to get the failed task result
                    result = invigilator.get_failed_task_result()
                else:
                    # No exception means the task completed successfully
                    pass
    
                yield result
    
    def _build_question_tasks(self, debug, model_buckets) -> List[asyncio.Task]:
        """Creates a task for each question, with dependencies on the questions that must be answered before this one can be answered."""
        logger.info("Creating tasks for each question")
        tasks = []
        invigilators = []
        for question in self.survey.questions:
            # finds dependency tasks for that question
            tasks_that_must_be_completed_before = (
                self._get_tasks_that_must_be_completed_before(tasks, question)
            )
            # creates the task for that question
            question_task = self._create_question_task(
                question = question, 
                tasks_that_must_be_completed_before = tasks_that_must_be_completed_before, 
                model_buckets = model_buckets,
                debug = debug
            )
            # adds the task to the list of tasks
            tasks.append(question_task)
            invigilators.append(self.get_invigilator(question, debug))
        return TasksList(tasks), invigilators

    def _get_tasks_that_must_be_completed_before(
        self, tasks, question
    ) -> List[asyncio.Task]:
        """Returns the tasks that must be completed before the given question can be answered.
        If a question has no dependencies, this will be an empty list, [].
        """
        parents_of_focal_question: List[str] = self.dag.get(question.question_name, [])
        return [
            tasks[self.to_index[parent_question_name]]
            for parent_question_name in parents_of_focal_question
        ]

    def _create_question_task(
        self,
        question: Question,
        tasks_that_must_be_completed_before: List[asyncio.Task],
        model_buckets: ModelBuckets,
        debug,
    ):
        """Creates a task that depends on the passed-in dependencies that are awaited before the task is run.
        """
        task_creator = QuestionTaskCreator(question = question, 
                                           func=self._answer_question_and_record_task, 
                                            token_estimator=self._get_estimated_request_tokens,
                                           model_buckets = model_buckets
                                           )
        [task_creator.add_dependency(x) for x in tasks_that_must_be_completed_before]
        self.task_creators[question.question_name] = task_creator
        return task_creator.generate_task(debug)

    def async_timeout_handler(timeout):
        def decorator(func):
            async def wrapper(*args, **kwargs):
                try:
                    return await asyncio.wait_for(func(*args, **kwargs), timeout)
                except asyncio.TimeoutError:
                    raise InterviewTimeoutError(
                        f"Task timed out after {timeout} seconds."
                    )

            return wrapper

        return decorator

    def get_invigilator(self, question, debug):
        invigilator = self.agent.create_invigilator(
            question=question,
            scenario=self.scenario,
            model=self.model,
            debug=debug,
            memory_plan=self.survey.memory_plan,
            current_answers=self.answers,
        )
        return invigilator

    def _get_estimated_request_tokens(self, question):
        """Estimates the number of tokens that will be required to run the focal task."""
        invigilator = self.get_invigilator(question, debug=False)
        #breakpoint()
        combined_text = ""
        for prompt in invigilator.get_prompts().values():
            if hasattr(prompt, "text"):
                combined_text += prompt.text
            elif isinstance(prompt, str):
                combined_text += prompt
            else:
                raise ValueError(f"Prompt is of type {type(prompt)}")
        return len(combined_text)/4.0

    @async_timeout_handler(TIMEOUT)
    async def _answer_question_and_record_task(
        self,
        question,
        debug,
    ) -> AgentResponseDict:
        """Answers a question and records the task.
        This in turn calls the the passed-in agent's async_answer_question method, which returns a response dictionary.
        """
        invigilator = self.get_invigilator(question, debug=debug)
        response: AgentResponseDict = await invigilator.async_answer_question()
        #breakpoint()
        response["question_name"] = question.question_name

        self.answers.add_answer(response, question)

        _ = self._cancel_skipped_questions(question)

        return response
    

    def _cancel_skipped_questions(self, current_question):
        """Cancels the tasks for questions that are skipped."""
        logger.info(f"Current question is {current_question.question_name}")
        self.tasks.status()
        current_question_index = self.to_index[current_question.question_name]
        next_question = self.survey.rule_collection.next_question(q_now=current_question_index, answers=self.answers)
        next_question_index = next_question.next_q

        def cancel_between(start, end):
            for i in range(start, end):
                logger.info(f"Cancelling task for question {i}; {self.tasks[i].edsl_name}")
                self.tasks[i].cancel()
                skipped_question_name = self.survey.question_names[i]
                logger.info(f"{skipped_question_name} skipped.")

        if next_question_index == EndOfSurvey:
            cancel_between(current_question_index + 1, len(self.survey.questions))
            return
        
        if next_question_index > (current_question_index + 1):
            cancel_between(current_question_index + 1, next_question_index)
        
        self.tasks.status()
    
     
    #######################
    # Dunder methods
    #######################
    def __repr__(self) -> str:
        """Returns a string representation of the Interview instance."""
        return f"Interview(agent = {self.agent}, survey = {self.survey}, scenario = {self.scenario}, model = {self.model})"


# def main():
#     from edsl.language_models import LanguageModelOpenAIThreeFiveTurbo
#     from edsl.agents import Agent
#     from edsl.surveys import Survey
#     from edsl.scenarios import Scenario
#     from edsl.questions import QuestionMultipleChoice

#     # from edsl.jobs.Interview import Interview

#     #  a survey with skip logic
#     q0 = QuestionMultipleChoice(
#         question_text="Do you like school?",
#         question_options=["yes", "no"],
#         question_name="q0",
#     )
#     q1 = QuestionMultipleChoice(
#         question_text="Why not?",
#         question_options=["killer bees in cafeteria", "other"],
#         question_name="q1",
#     )
#     q2 = QuestionMultipleChoice(
#         question_text="Why?",
#         question_options=["**lack*** of killer bees in cafeteria", "other"],
#         question_name="q2",
#     )
#     s = Survey(questions=[q0, q1, q2])
#     s = s.add_rule(q0, "q0 == 'yes'", q2)

#     # create an interview
#     a = Agent(traits=None)

#     def direct_question_answering_method(self, question, scenario):
#         return "yes"

#     a.add_direct_question_answering_method(direct_question_answering_method)
#     scenario = Scenario()
#     m = LanguageModelOpenAIThreeFiveTurbo(use_cache=False)
#     I = Interview(agent=a, survey=s, scenario=scenario, model=m)

#     I.conduct_interview()
#     # # conduct five interviews
#     # for _ in range(5):
#     #     I.conduct_interview(debug=True)

#     # # replace missing answers
#     # I
#     # repr(I)
#     # eval(repr(I))


if __name__ == "__main__":
    from edsl.language_models import LanguageModelOpenAIThreeFiveTurbo
    from edsl.agents import Agent
    from edsl.surveys import Survey
    from edsl.scenarios import Scenario
    from edsl.questions import QuestionMultipleChoice

    # from edsl.jobs.Interview import Interview

    #  a survey with skip logic
    q0 = QuestionMultipleChoice(
        question_text="Do you like school?",
        question_options=["yes", "no"],
        question_name="q0",
    )
    q1 = QuestionMultipleChoice(
        question_text="Why not?",
        question_options=["killer bees in cafeteria", "other"],
        question_name="q1",
    )
    q2 = QuestionMultipleChoice(
        question_text="Why?",
        question_options=["**lack*** of killer bees in cafeteria", "other"],
        question_name="q2",
    )
    s = Survey(questions=[q0, q1, q2])
    s = s.add_rule(q0, "q0 == 'yes'", q2)

    # create an interview
    a = Agent(traits=None)

    def direct_question_answering_method(self, question, scenario):
        return "yes"

    a.add_direct_question_answering_method(direct_question_answering_method)
    scenario = Scenario()
    m = LanguageModelOpenAIThreeFiveTurbo(use_cache=False)
    I = Interview(agent=a, survey=s, scenario=scenario, model=m)

    I.conduct_interview()
    # # conduct five interviews
    # for _ in range(5):
    #     I.conduct_interview(debug=True)

    # # replace missing answers
    # I
    # repr(I)
    # eval(repr(I))
