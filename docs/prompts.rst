.. _prompts:

Prompts
=======

Overview
--------

Prompts are texts that are sent to a language model in order to guide it on how to generate responses to questions.
They can include questions, instructions or any other textual information to be displayed to the language model.


Creating & showing prompts
--------------------------

There are two types of prompts:

* A `user_prompt` contains the instructions for a question.
* A `system_prompt` contains the instructions for the agent. 

*Note: Some models do not support system prompts, e.g., OpenAI's o1 models. 
When using these models the system prompts will be ignored.*


Methods 
^^^^^^^

Methods for displaying prompts are available for both surveys and jobs:

* Calling the `show_prompts()` method on a `Survey` will display the user prompts and the system prompts (if any agents are used) that will be sent to the model when the survey is run.
* Calling the `prompts()` method on a `Job` (a survey combined with a model) will return a dataset of the prompts together with information about each question/scenario/agent/model combination and estimated cost.

For example, here we create a survey consisting of a single question and use the `show_prompts()` method to inspect the prompts without adding an agent:

.. code-block:: python

   from edsl import QuestionFreeText, Survey

   q = QuestionFreeText(
      question_name = "today",
      question_text = "How do you feel today?"
   )

   survey = Survey([q])

   survey.show_prompts()


Output:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓
   ┃ user_prompt            ┃ system_prompt ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩
   │ How do you feel today? │               │
   └────────────────────────┴───────────────┘


In this example, the `user_prompt` is identical to the question text because there are no default additional instructions for free text questions, and the `system_prompt` is blank because we did not use an agent.

Here we create an agent, add it to the survey and show the prompts again:

.. code-block:: python

   from edsl import QuestionFreeText, Survey, Agent

   q = QuestionFreeText(
      question_name = "today",
      question_text = "How do you feel today?"
   )

   agent = Agent(
      traits = {
         "persona": "You are a high school student.",
         "age": 15
      }
   )

   survey = Survey([q])

   survey.by(agent).show_prompts()


Output:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ user_prompt            ┃ system_prompt                                                                          ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
   │ How do you feel today? │ You are answering questions as if you were a human. Do not break character. Your       │
   │                        │ traits: {'persona': 'You are a high school student.', 'age': 15}                       │
   └────────────────────────┴────────────────────────────────────────────────────────────────────────────────────────┘


This time we can see that the `system_prompt` includes the default agent instructions (*You are answering questions as if you were a human. Do not break character. Your traits:*) and the agent's traits.

If we want to see more information about the question, we can create a job that combines the survey and a model, and call the `prompts()` method:

.. code-block:: python

   from edsl import Model

   model = Model("gpt-4o")

   survey.by(agent).by(model).prompts().print(format="rich") # to display the prompts in a rich format


Output:

.. code-block:: text

   ┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━┓
   ┃ user_prompt  ┃ system_prom… ┃ interview_i… ┃ question_na… ┃ scenario_ind… ┃ agent_index ┃ model  ┃ estimated_c… ┃
   ┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━┩
   │ How do you   │ You are      │ 0            │ today        │ 0             │ 0           │ gpt-4o │ 3.074999999… │
   │ feel today?  │ answering    │              │              │               │             │        │              │
   │              │ questions as │              │              │               │             │        │              │
   │              │ if you were  │              │              │               │             │        │              │
   │              │ a human. Do  │              │              │               │             │        │              │
   │              │ not break    │              │              │               │             │        │              │
   │              │ character.   │              │              │               │             │        │              │
   │              │ Your traits: │              │              │               │             │        │              │
   │              │ {'persona':  │              │              │               │             │        │              │
   │              │ 'You are a   │              │              │               │             │        │              │
   │              │ high school  │              │              │               │             │        │              │
   │              │ student.',   │              │              │               │             │        │              │
   │              │ 'age': 15}   │              │              │               │             │        │              │
   └──────────────┴──────────────┴──────────────┴──────────────┴───────────────┴─────────────┴────────┴──────────────┘


Modifying agent instructions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

An agent can also be constructed with an optional `instruction`.
This text is added to the beginning of the `system_prompt`, replacing the default instructions *"You are answering questions as if you were a human. Do not break character."*
Here we create agents with and without an instruction and compare the prompts:

.. code-block:: python

   from edsl import AgentList, Agent

   agents = AgentList([
      Agent(
         traits = {"persona": "You are a high school student.", "age": 15}
         # no instruction
      ),
      Agent(
         traits = {"persona": "You are a high school student.", "age": 15}, 
         instruction = "You are tired."
      )
   ])

   survey.by(agents).show_prompts() # using the survey from the previous examples


Output:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ user_prompt            ┃ system_prompt                                                                          ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
   │ How do you feel today? │ You are answering questions as if you were a human. Do not break character. Your       │
   │                        │ traits: {'persona': 'You are a high school student.', 'age': 15}                       │
   ├────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
   │ How do you feel today? │ You are tired. Your traits: {'persona': 'You are a high school student.', 'age': 15}   │
   └────────────────────────┴────────────────────────────────────────────────────────────────────────────────────────┘


If we use the `prompts()` method to see more details, we will find that the `agent_index` is different for each agent, allowing us to distinguish between them in the survey results, and the `interview_index` is also incremented for each question/agent/model combination:

.. code-block:: python

   survey.by(agents).by(model).prompts().print(format="rich") # using the survey, agents and model from examples above


Output:

.. code-block:: text 

   ┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━┓
   ┃ user_prompt  ┃ system_prom… ┃ interview_i… ┃ question_na… ┃ scenario_ind… ┃ agent_index ┃ model  ┃ estimated_c… ┃
   ┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━┩
   │ How do you   │ You are      │ 0            │ today        │ 0             │ 0           │ gpt-4o │ 3.074999999… │
   │ feel today?  │ answering    │              │              │               │             │        │              │
   │              │ questions as │              │              │               │             │        │              │
   │              │ if you were  │              │              │               │             │        │              │
   │              │ a human. Do  │              │              │               │             │        │              │
   │              │ not break    │              │              │               │             │        │              │
   │              │ character.   │              │              │               │             │        │              │
   │              │ Your traits: │              │              │               │             │        │              │
   │              │ {'persona':  │              │              │               │             │        │              │
   │              │ 'You are a   │              │              │               │             │        │              │
   │              │ high school  │              │              │               │             │        │              │
   │              │ student.',   │              │              │               │             │        │              │
   │              │ 'age': 15}   │              │              │               │             │        │              │
   ├──────────────┼──────────────┼──────────────┼──────────────┼───────────────┼─────────────┼────────┼──────────────┤
   │ How do you   │ You are      │ 1            │ today        │ 0             │ 1           │ gpt-4o │ 1.95e-05     │
   │ feel today?  │ tired. Your  │              │              │               │             │        │              │
   │              │ traits:      │              │              │               │             │        │              │
   │              │ {'persona':  │              │              │               │             │        │              │
   │              │ 'You are a   │              │              │               │             │        │              │
   │              │ high school  │              │              │               │             │        │              │
   │              │ student.',   │              │              │               │             │        │              │
   │              │ 'age': 15}   │              │              │               │             │        │              │
   └──────────────┴──────────────┴──────────────┴──────────────┴───────────────┴─────────────┴────────┴──────────────┘


Agent names 
^^^^^^^^^^^

Agents can also be constructed with an optional unique `name` parameter which does *not* appear in the prompts but can be useful for identifying agents in the results.
The name is stored in the `agent_name` column that is automatically added to the results.
The default agent name in results is "Agent" followed by the agent's index in the agent list (e.g. "Agent_0", "Agent_1", etc.).

Learn more about designing :ref:`agents` and accessing columns in :ref:`results`.


Instructions for question types
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In the examples above, the `user_prompt` for the question was identical to the question text.
This is because the question type was free text, which does not include additional instructions by default.
Question types other than free text include additional instructions in the `user_prompt` that are specific to the question type.

For example, here we create a multiple choice question and inspect the user prompt:

.. code-block:: python

   from edsl import QuestionMultipleChoice, Survey

   q = QuestionMultipleChoice(
      question_name = "favorite_subject",
      question_text = "What is your favorite subject?",
      question_options = ["Math", "English", "Social studies", "Science", "Other"]
   )

   survey = Survey([q])

   survey.by(agent).prompts().select("user_prompt").print(format="rich") # to display just the user prompt


Output:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ user_prompt                                                                                    ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
   │                                                                                                │
   │ What is your favorite subject?                                                                 │
   │                                                                                                │
   │                                                                                                │
   │ Math                                                                                           │
   │                                                                                                │
   │ English                                                                                        │
   │                                                                                                │
   │ Social studies                                                                                 │
   │                                                                                                │
   │ Science                                                                                        │
   │                                                                                                │
   │ Other                                                                                          │
   │                                                                                                │
   │                                                                                                │
   │ Only 1 option may be selected.                                                                 │
   │                                                                                                │
   │ Respond only with a string corresponding to one of the options.                                │
   │                                                                                                │
   │                                                                                                │
   │ After the answer, you can put a comment explaining why you chose that option on the next line. │
   └────────────────────────────────────────────────────────────────────────────────────────────────┘


In this case, the `user_prompt` for the question includes both the question text and the default instructions for multiple choice questions: *"Only one answer may be selected..."*
Other question types have their own default instructions that specify how the response should be formatted.

Learn more about the different question types in the :ref:`questions` section of the documentation.


Comments
^^^^^^^^

The user prompt for the multiple choice question above also includes an instruction for the model to provide a comment about its answer: *"After the answer, you can put a comment explaining why you chose that option on the next line."*
All questions types other than free text automatically include a "comment" which is stored in a separate field in the survey results.
(The field is blank for free text questions.)
Comments are not required, but can be useful for understanding a model's reasoning, or debugging a non-response.
They can also be useful when you want to simulate a "chain of thought" by giving an agent context of prior questions and answers in a survey.
Comments can be turned off by passing a parameter `include_comment = False` to the question constructor.

Learn more about using question memory and piping comments or other question components in the :ref:`surveys` section of the documentation.

For example, here we modify the multiple choice question above to not include a comment and show the resulting user prompt:

.. code-block:: python

   from edsl import QuestionMultipleChoice, Survey

   q = QuestionMultipleChoice(
      question_name = "favorite_subject",
      question_text = "What is your favorite subject?",
      question_options = ["Math", "English", "Social studies", "Science", "Other"],
      include_comment = False
   )

   survey = Survey([q])

   survey.by(agent).prompts().select("user_prompt").print(format="rich") # using the agent and model from previous examples


Output:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ user_prompt                                                     ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
   │                                                                 │
   │ What is your favorite subject?                                  │
   │                                                                 │
   │                                                                 │
   │ Math                                                            │
   │                                                                 │
   │ English                                                         │
   │                                                                 │
   │ Social studies                                                  │
   │                                                                 │
   │ Science                                                         │
   │                                                                 │
   │ Other                                                           │
   │                                                                 │
   │                                                                 │
   │ Only 1 option may be selected.                                  │
   │                                                                 │
   │ Respond only with a string corresponding to one of the options. │
   └─────────────────────────────────────────────────────────────────┘


There is no longer any instruction about a comment at the end of the user prompt.


Prompts for multiple questions 
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If a survey consists of multiple questions, the `show_prompts()` and `prompts()` methods will display all of the prompts for each question/scenario/model/agent combination in the survey.

For example:

.. code-block:: python

   from edsl import QuestionMultipleChoice, QuestionYesNo, Survey

   q1 = QuestionMultipleChoice(
      question_name = "favorite_subject",
      question_text = "What is your favorite subject?",
      question_options = ["Math", "English", "Social studies", "Science", "Other"]
   )

   q2 = QuestionYesNo(
      question_name = "college_plan",
      question_text = "Do you plan to go to college?"
   )

   survey = Survey([q1, q2])

   survey.by(agent).by(model).prompts().print(format="rich") # using the agent and model from previous examples


Output:

.. code-block:: text

   ┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━┓
   ┃ user_prompt  ┃ system_prom… ┃ interview_i… ┃ question_na… ┃ scenario_in… ┃ agent_index ┃ model  ┃ estimated_co… ┃
   ┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━┩
   │              │ You are      │ 0            │ favorite_su… │ 0            │ 0           │ gpt-4o │ 8.2499999999… │
   │ What is your │ answering    │              │              │              │             │        │               │
   │ favorite     │ questions as │              │              │              │             │        │               │
   │ subject?     │ if you were  │              │              │              │             │        │               │
   │              │ a human. Do  │              │              │              │             │        │               │
   │              │ not break    │              │              │              │             │        │               │
   │ Math         │ character.   │              │              │              │             │        │               │
   │              │ Your traits: │              │              │              │             │        │               │
   │ English      │ {'persona':  │              │              │              │             │        │               │
   │              │ 'You are a   │              │              │              │             │        │               │
   │ Social       │ high school  │              │              │              │             │        │               │
   │ studies      │ student.',   │              │              │              │             │        │               │
   │              │ 'age': 15}   │              │              │              │             │        │               │
   │ Science      │              │              │              │              │             │        │               │
   │              │              │              │              │              │             │        │               │
   │ Other        │              │              │              │              │             │        │               │
   │              │              │              │              │              │             │        │               │
   │              │              │              │              │              │             │        │               │
   │ Only 1       │              │              │              │              │             │        │               │
   │ option may   │              │              │              │              │             │        │               │
   │ be selected. │              │              │              │              │             │        │               │
   │              │              │              │              │              │             │        │               │
   │ Respond only │              │              │              │              │             │        │               │
   │ with a       │              │              │              │              │             │        │               │
   │ string       │              │              │              │              │             │        │               │
   │ correspondi… │              │              │              │              │             │        │               │
   │ to one of    │              │              │              │              │             │        │               │
   │ the options. │              │              │              │              │             │        │               │
   │              │              │              │              │              │             │        │               │
   │              │              │              │              │              │             │        │               │
   │ After the    │              │              │              │              │             │        │               │
   │ answer, you  │              │              │              │              │             │        │               │
   │ can put a    │              │              │              │              │             │        │               │
   │ comment      │              │              │              │              │             │        │               │
   │ explaining   │              │              │              │              │             │        │               │
   │ why you      │              │              │              │              │             │        │               │
   │ chose that   │              │              │              │              │             │        │               │
   │ option on    │              │              │              │              │             │        │               │
   │ the next     │              │              │              │              │             │        │               │
   │ line.        │              │              │              │              │             │        │               │
   ├──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼─────────────┼────────┼───────────────┤
   │              │ You are      │ 0            │ college_plan │ 0            │ 0           │ gpt-4o │ 6.3e-05       │
   │ Do you plan  │ answering    │              │              │              │             │        │               │
   │ to go to     │ questions as │              │              │              │             │        │               │
   │ college?     │ if you were  │              │              │              │             │        │               │
   │              │ a human. Do  │              │              │              │             │        │               │
   │              │ not break    │              │              │              │             │        │               │
   │ No           │ character.   │              │              │              │             │        │               │
   │              │ Your traits: │              │              │              │             │        │               │
   │ Yes          │ {'persona':  │              │              │              │             │        │               │
   │              │ 'You are a   │              │              │              │             │        │               │
   │              │ high school  │              │              │              │             │        │               │
   │ Only 1       │ student.',   │              │              │              │             │        │               │
   │ option may   │ 'age': 15}   │              │              │              │             │        │               │
   │ be selected. │              │              │              │              │             │        │               │
   │ Please       │              │              │              │              │             │        │               │
   │ respond with │              │              │              │              │             │        │               │
   │ just your    │              │              │              │              │             │        │               │
   │ answer.      │              │              │              │              │             │        │               │
   │              │              │              │              │              │             │        │               │
   │              │              │              │              │              │             │        │               │
   │ After the    │              │              │              │              │             │        │               │
   │ answer, you  │              │              │              │              │             │        │               │
   │ can put a    │              │              │              │              │             │        │               │
   │ comment      │              │              │              │              │             │        │               │
   │ explaining   │              │              │              │              │             │        │               │
   │ your         │              │              │              │              │             │        │               │
   │ response.    │              │              │              │              │             │        │               │
   └──────────────┴──────────────┴──────────────┴──────────────┴──────────────┴─────────────┴────────┴───────────────┘


Modifying prompts
-----------------

Templates for default prompts are provided in the `edsl.prompts.library` module.
These prompts can be used as is or customized to suit specific requirements by creating new classes that inherit from the `Prompt` class.

Typically, prompts are created using the `Prompt` class, a subclass of the `PromptBase` class which is an abstract class that defines the basic structure of a prompt.
The `Prompt` class has the following attributes (see examples above):

- `user_prompt`: A list of strings that contain the text that will be sent to the model.
- `system_prompt`: A list of strings that contain the text that will be sent to the model.
- `interview_index`: An integer that specifies the index of the interview.
- `question_name`: A string that specifies the name of the question.
- `scenario_index`: An integer that specifies the index of the scenario.
- `agent_index`: An integer that specifies the index of the agent.
- `model`: A string that specifies the model to be used.
- `estimated_cost`: A float that specifies the estimated cost of the prompt.


Inspecting prompts after running a survey
-----------------------------------------

After a survey is run, we can inspect the prompts that were used by selecting the `prompt.*` fields of the results.

For example, here we run the survey from above and inspect the prompts that were used:

.. code-block:: python 
   
   results = survey.by(agent).by(model).run() 


To select all the `prompt` columns at once:

.. code-block:: python

   results.select("prompt.*").print(format="rich") 


Output:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ prompt                    ┃ prompt                     ┃ prompt                    ┃ prompt                     ┃
   ┃ .favorite_subject_user_p… ┃ .college_plan_system_prom… ┃ .favorite_subject_system… ┃ .college_plan_user_prompt  ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
   │                           │ You are answering          │ You are answering         │                            │
   │ What is your favorite     │ questions as if you were a │ questions as if you were  │ Do you plan to go to       │
   │ subject?                  │ human. Do not break        │ a human. Do not break     │ college?                   │
   │                           │ character. You are an      │ character. You are an     │                            │
   │                           │ agent with the following   │ agent with the following  │                            │
   │ Math                      │ persona:                   │ persona:                  │ No                         │
   │                           │ {'persona': 'You are a     │ {'persona': 'You are a    │                            │
   │ English                   │ high school student.',     │ high school student.',    │ Yes                        │
   │                           │ 'age': 15}                 │ 'age': 15}                │                            │
   │ Social studies            │                            │                           │                            │
   │                           │                            │                           │ Only 1 option may be       │
   │ Science                   │                            │                           │ selected.                  │
   │                           │                            │                           │ Please respond with just   │
   │ Other                     │                            │                           │ your answer.               │
   │                           │                            │                           │                            │
   │                           │                            │                           │                            │
   │ Only 1 option may be      │                            │                           │ After the answer, you can  │
   │ selected.                 │                            │                           │ put a comment explaining   │
   │                           │                            │                           │ your response.             │
   │ Respond only with a       │                            │                           │                            │
   │ string corresponding to   │                            │                           │                            │
   │ one of the options.       │                            │                           │                            │
   │                           │                            │                           │                            │
   │                           │                            │                           │                            │
   │ After the answer, you can │                            │                           │                            │
   │ put a comment explaining  │                            │                           │                            │
   │ why you chose that option │                            │                           │                            │
   │ on the next line.         │                            │                           │                            │
   └───────────────────────────┴────────────────────────────┴───────────────────────────┴────────────────────────────┘


Or to specify the order in the table we can name them individually:

.. code-block:: python

   (
      results.select(
         "favorite_subject_system_prompt",
         "college_plan_system_prompt",
         "favorite_subject_user_prompt",
         "college_plan_user_prompt"
      )
      .print(format="rich")
   )


Output:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ prompt                    ┃ prompt                     ┃ prompt                    ┃ prompt                     ┃
   ┃ .favorite_subject_system… ┃ .college_plan_system_prom… ┃ .favorite_subject_user_p… ┃ .college_plan_user_prompt  ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
   │ You are answering         │ You are answering          │                           │                            │
   │ questions as if you were  │ questions as if you were a │ What is your favorite     │ Do you plan to go to       │
   │ a human. Do not break     │ human. Do not break        │ subject?                  │ college?                   │
   │ character. You are an     │ character. You are an      │                           │                            │
   │ agent with the following  │ agent with the following   │                           │                            │
   │ persona:                  │ persona:                   │ Math                      │ No                         │
   │ {'persona': 'You are a    │ {'persona': 'You are a     │                           │                            │
   │ high school student.',    │ high school student.',     │ English                   │ Yes                        │
   │ 'age': 15}                │ 'age': 15}                 │                           │                            │
   │                           │                            │ Social studies            │                            │
   │                           │                            │                           │ Only 1 option may be       │
   │                           │                            │ Science                   │ selected.                  │
   │                           │                            │                           │ Please respond with just   │
   │                           │                            │ Other                     │ your answer.               │
   │                           │                            │                           │                            │
   │                           │                            │                           │                            │
   │                           │                            │ Only 1 option may be      │ After the answer, you can  │
   │                           │                            │ selected.                 │ put a comment explaining   │
   │                           │                            │                           │ your response.             │
   │                           │                            │ Respond only with a       │                            │
   │                           │                            │ string corresponding to   │                            │
   │                           │                            │ one of the options.       │                            │
   │                           │                            │                           │                            │
   │                           │                            │                           │                            │
   │                           │                            │ After the answer, you can │                            │
   │                           │                            │ put a comment explaining  │                            │
   │                           │                            │ why you chose that option │                            │
   │                           │                            │ on the next line.         │                            │
   └───────────────────────────┴────────────────────────────┴───────────────────────────┴────────────────────────────┘


More about question prompts
---------------------------

See the :ref:`questions` section for `more details <https://docs.expectedparrot.com/en/latest/questions.html#optional-additional-parameters>`_ on how to create and customize question prompts with `question_presentation` and `answering_instructions` parameters in the `Question` type constructor.


Prompts class 
-------------

.. automodule:: edsl.prompts.Prompt
   :members: 
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members:
