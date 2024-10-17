.. _prompts:

Prompts
=======

Overview
--------

Prompts are texts that are sent to a language model in order to guide it on how to generate responses to questions.
They can include questions, instructions or any other textual information to be displayed to the language model.


Creating & showing prompts
--------------------------

Prompts are generated automatically when a `Question` or `Survey` is combined with a `Model` and (optionally) an `Agent`, creating a `Job`.
The job contains the prompts that will be sent to the model: each `user_prompt` contains the instructions for a question and each `system_prompt` contains the instructions for the agent. 
We can inspect these prompts by calling the `show_prompts()` method on the job.

For example, here we create a job with a single question and show the prompts that will be used when the survey is run:

.. code-block:: python

   from edsl import QuestionFreeText, Model

   q = QuestionFreeText(
      question_name = "today",
      question_text = "How do you feel today?"
   )

   m = Model("gpt-4o")

   job = q.by(m)

   job.show_prompts()


Output:

.. code-block:: text

   ┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━┓
   ┃ user_prompt  ┃ system_prom… ┃ interview_i… ┃ question_na… ┃ scenario_ind… ┃ agent_index ┃ model  ┃ estimated_c… ┃
   ┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━┩
   │ How do you   │              │ 0            │ today        │ 0             │ 0           │ gpt-4o │ 6.25e-05     │
   │ feel today?  │              │              │              │               │             │        │              │
   └──────────────┴──────────────┴──────────────┴──────────────┴───────────────┴─────────────┴────────┴──────────────┘


In this example, the `user_prompt` is the question text (there are no default additional instructions for free text questions) 
and the `system_prompt` is blank because we are not using an agent.

Here we add an agent to the job and show the prompts again:

.. code-block:: python

   from edsl import Agent

   a = Agent(traits = {
      "persona": "You are a high school student.",
      "age": 15
   })

   job = q.by(a).by(m) # using the agent and model from the previous example

   job.show_prompts()


Output:

.. code-block:: text

   ┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━┓
   ┃ user_prompt  ┃ system_prom… ┃ interview_i… ┃ question_na… ┃ scenario_ind… ┃ agent_index ┃ model  ┃ estimated_c… ┃
   ┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━┩
   │ How do you   │ You are      │ 0            │ today        │ 0             │ 0           │ gpt-4o │ 0.0006125    │
   │ feel today?  │ answering    │              │              │               │             │        │              │
   │              │ questions as │              │              │               │             │        │              │
   │              │ if you were  │              │              │               │             │        │              │
   │              │ a human. Do  │              │              │               │             │        │              │
   │              │ not break    │              │              │               │             │        │              │
   │              │ character.   │              │              │               │             │        │              │
   │              │ You are an   │              │              │               │             │        │              │
   │              │ agent with   │              │              │               │             │        │              │
   │              │ the          │              │              │               │             │        │              │
   │              │ following    │              │              │               │             │        │              │
   │              │ persona:     │              │              │               │             │        │              │
   │              │ {'persona':  │              │              │               │             │        │              │
   │              │ 'You are a   │              │              │               │             │        │              │
   │              │ high school  │              │              │               │             │        │              │
   │              │ student.',   │              │              │               │             │        │              │
   │              │ 'age': 15}   │              │              │               │             │        │              │
   └──────────────┴──────────────┴──────────────┴──────────────┴───────────────┴─────────────┴────────┴──────────────┘


This time we can see that the `system_prompt` include the default agent instructions and the agent's traits.

If the job is for a survey of multiple questions, we will see all the prompts in the table that is displayed:

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

   job = survey.by(a).by(m) # using the agent and model from the previous example

   job.show_prompts()


Output:

.. code-block:: text

   ┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━┓
   ┃ user_prompt  ┃ system_prom… ┃ interview_i… ┃ question_na… ┃ scenario_in… ┃ agent_index ┃ model  ┃ estimated_co… ┃
   ┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━┩
   │              │ You are      │ 0            │ favorite_su… │ 0            │ 0           │ gpt-4o │ 0.0014750000… │
   │ What is your │ answering    │              │              │              │             │        │               │
   │ favorite     │ questions as │              │              │              │             │        │               │
   │ subject?     │ if you were  │              │              │              │             │        │               │
   │              │ a human. Do  │              │              │              │             │        │               │
   │              │ not break    │              │              │              │             │        │               │
   │ Math         │ character.   │              │              │              │             │        │               │
   │              │ You are an   │              │              │              │             │        │               │
   │ English      │ agent with   │              │              │              │             │        │               │
   │              │ the          │              │              │              │             │        │               │
   │ Social       │ following    │              │              │              │             │        │               │
   │ studies      │ persona:     │              │              │              │             │        │               │
   │              │ {'persona':  │              │              │              │             │        │               │
   │ Science      │ 'You are a   │              │              │              │             │        │               │
   │              │ high school  │              │              │              │             │        │               │
   │ Other        │ student.',   │              │              │              │             │        │               │
   │              │ 'age': 15}   │              │              │              │             │        │               │
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
   │              │ You are      │ 0            │ college_plan │ 0            │ 0           │ gpt-4o │ 0.00115       │
   │ Do you plan  │ answering    │              │              │              │             │        │               │
   │ to go to     │ questions as │              │              │              │             │        │               │
   │ college?     │ if you were  │              │              │              │             │        │               │
   │              │ a human. Do  │              │              │              │             │        │               │
   │              │ not break    │              │              │              │             │        │               │
   │ No           │ character.   │              │              │              │             │        │               │
   │              │ You are an   │              │              │              │             │        │               │
   │ Yes          │ agent with   │              │              │              │             │        │               │
   │              │ the          │              │              │              │             │        │               │
   │              │ following    │              │              │              │             │        │               │
   │ Only 1       │ persona:     │              │              │              │             │        │               │
   │ option may   │ {'persona':  │              │              │              │             │        │               │
   │ be selected. │ 'You are a   │              │              │              │             │        │               │
   │ Please       │ high school  │              │              │              │             │        │               │
   │ respond with │ student.',   │              │              │              │             │        │               │
   │ just your    │ 'age': 15}   │              │              │              │             │        │               │
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


In this case, the `user_prompt` for each question includes both the question text and the default instructions for the question type, which include an instruction to provide a comment after the answer.
All questions types other than free text questions include a "comment" field (a separate column in the survey results) where the model can provide additional information about its answer.
Comments are not required, but can be useful for understanding the model's reasoning, or debugging a non-response.
They can also be useful when you want to simulate a "chain of thought" where an agent is given context of prior questions and answers in a survey.
(Learn more about adding question memory and piping question components and answers in the :ref:`surveys` section of the documentation.)
Comments can be turned off by passing a parameter `include_comment = False` to the question constructor.

For example, here we modify the questions above to not include comments and show the resulting prompts:

.. code-block:: python

   q1 = QuestionMultipleChoice(
      question_name = "favorite_subject",
      question_text = "What is your favorite subject?",
      question_options = ["Math", "English", "Social studies", "Science", "Other"],
      include_comment = False
   )

   q2 = QuestionYesNo(
      question_name = "college_plan",
      question_text = "Do you plan to go to college?",
      include_comment = False
   )

   survey = Survey([q1, q2])

   job = survey.by(a).by(m) # using the agent and model from the previous example

   job.show_prompts()


Output:

.. code-block:: text

   ┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━┓
   ┃ user_prompt  ┃ system_prom… ┃ interview_i… ┃ question_na… ┃ scenario_in… ┃ agent_index ┃ model  ┃ estimated_co… ┃
   ┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━┩
   │              │ You are      │ 0            │ favorite_su… │ 0            │ 0           │ gpt-4o │ 0.001175      │
   │ What is your │ answering    │              │              │              │             │        │               │
   │ favorite     │ questions as │              │              │              │             │        │               │
   │ subject?     │ if you were  │              │              │              │             │        │               │
   │              │ a human. Do  │              │              │              │             │        │               │
   │              │ not break    │              │              │              │             │        │               │
   │ Math         │ character.   │              │              │              │             │        │               │
   │              │ You are an   │              │              │              │             │        │               │
   │ English      │ agent with   │              │              │              │             │        │               │
   │              │ the          │              │              │              │             │        │               │
   │ Social       │ following    │              │              │              │             │        │               │
   │ studies      │ persona:     │              │              │              │             │        │               │
   │              │ {'persona':  │              │              │              │             │        │               │
   │ Science      │ 'You are a   │              │              │              │             │        │               │
   │              │ high school  │              │              │              │             │        │               │
   │ Other        │ student.',   │              │              │              │             │        │               │
   │              │ 'age': 15}   │              │              │              │             │        │               │
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
   ├──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼─────────────┼────────┼───────────────┤
   │              │ You are      │ 0            │ college_plan │ 0            │ 0           │ gpt-4o │ 0.0009375     │
   │ Do you plan  │ answering    │              │              │              │             │        │               │
   │ to go to     │ questions as │              │              │              │             │        │               │
   │ college?     │ if you were  │              │              │              │             │        │               │
   │              │ a human. Do  │              │              │              │             │        │               │
   │              │ not break    │              │              │              │             │        │               │
   │ No           │ character.   │              │              │              │             │        │               │
   │              │ You are an   │              │              │              │             │        │               │
   │ Yes          │ agent with   │              │              │              │             │        │               │
   │              │ the          │              │              │              │             │        │               │
   │              │ following    │              │              │              │             │        │               │
   │ Only 1       │ persona:     │              │              │              │             │        │               │
   │ option may   │ {'persona':  │              │              │              │             │        │               │
   │ be selected. │ 'You are a   │              │              │              │             │        │               │
   │ Please       │ high school  │              │              │              │             │        │               │
   │ respond with │ student.',   │              │              │              │             │        │               │
   │ just your    │ 'age': 15}   │              │              │              │             │        │               │
   │ answer.      │              │              │              │              │             │        │               │
   └──────────────┴──────────────┴──────────────┴──────────────┴──────────────┴─────────────┴────────┴───────────────┘


If we want to view just the prompts, we can call the `prompts()` method on the job to generate the information as a dataset, and then select the `user_prompt` and `system_prompt` columns:

.. code-block:: python

   job.prompts().select("user_prompt", "system_prompt").print(format="rich")


Output (note that comments have been turned off in this example):

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ user_prompt                                            ┃ system_prompt                                          ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
   │                                                        │ You are answering questions as if you were a human. Do │
   │ What is your favorite subject?                         │ not break character. You are an agent with the         │
   │                                                        │ following persona:                                     │
   │                                                        │ {'persona': 'You are a high school student.', 'age':   │
   │ Math                                                   │ 15}                                                    │
   │                                                        │                                                        │
   │ English                                                │                                                        │
   │                                                        │                                                        │
   │ Social studies                                         │                                                        │
   │                                                        │                                                        │
   │ Science                                                │                                                        │
   │                                                        │                                                        │
   │ Other                                                  │                                                        │
   │                                                        │                                                        │
   │                                                        │                                                        │
   │ Only 1 option may be selected.                         │                                                        │
   │                                                        │                                                        │
   │ Respond only with a string corresponding to one of the │                                                        │
   │ options.                                               │                                                        │
   ├────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────┤
   │                                                        │ You are answering questions as if you were a human. Do │
   │ Do you plan to go to college?                          │ not break character. You are an agent with the         │
   │                                                        │ following persona:                                     │
   │                                                        │ {'persona': 'You are a high school student.', 'age':   │
   │ No                                                     │ 15}                                                    │
   │                                                        │                                                        │
   │ Yes                                                    │                                                        │
   │                                                        │                                                        │
   │                                                        │                                                        │
   │ Only 1 option may be selected.                         │                                                        │
   │ Please respond with just your answer.                  │                                                        │
   └────────────────────────────────────────────────────────┴────────────────────────────────────────────────────────┘


Prompts as a dataset 
--------------------

We can call the `prompts()` method on a job to generate the information as a dataset:

.. code-block:: python

   prompts = job.prompts()
   prompts 


Output:

.. code-block:: text

   edsl.results.Dataset.Dataset


.. code-block:: python

   prompts 


Output (note that comments have been turned off in this example):

.. code-block:: text

   [
      {
         "user_prompt": [
               "\nWhat is your favorite subject?\n\n    \nMath\n    \nEnglish\n    \nSocial studies\n    \nScience\n    \nOther\n    \n\nOnly 1 option may be selected.\n\nRespond only with a string corresponding to one of the options.",
               "\nDo you plan to go to college?\n\n    \nNo\n    \nYes\n    \n\nOnly 1 option may be selected.\nPlease respond with just your answer."
         ]
      },
      {
         "system_prompt": [
               "You are answering questions as if you were a human. Do not break character. You are an agent with the following persona:\n{'persona': 'You are a high school student.', 'age': 15}",
               "You are answering questions as if you were a human. Do not break character. You are an agent with the following persona:\n{'persona': 'You are a high school student.', 'age': 15}"
         ]
      },
      {
         "interview_index": [
               0,
               0
         ]
      },
      {
         "question_name": [
               "favorite_subject",
               "college_plan"
         ]
      },
      {
         "scenario_index": [
               0,
               0
         ]
      },
      {
         "agent_index": [
               0,
               0
         ]
      },
      {
         "model": [
               "gpt-4o",
               "gpt-4o"
         ]
      },
      {
         "estimated_cost": [
               0.0014750000000000002,
               0.00115
         ]
      }
   ]


We can select any components to print as a table:

.. code-block:: python

   prompts.select("user_prompt").print(format="rich")


Output (note that comments have been turned off in this example):

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
   ├────────────────────────────────────────────────────────────────────────────────────────────────┤
   │                                                                                                │
   │ Do you plan to go to college?                                                                  │
   │                                                                                                │
   │                                                                                                │
   │ No                                                                                             │
   │                                                                                                │
   │ Yes                                                                                            │
   │                                                                                                │
   │                                                                                                │
   │ Only 1 option may be selected.                                                                 │
   │ Please respond with just your answer.                                                          │
   └────────────────────────────────────────────────────────────────────────────────────────────────┘


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

   results = job.run() # using the job from the previous example
   

This is equivalent to running `results = survey.by(a).by(m).run()`.

To select all the `prompt` columns at once:

.. code-block:: python

   results.select("prompt.*").print(format="rich") 


Output (note that comments have been turned off in this example):

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ prompt                     ┃ prompt                    ┃ prompt                     ┃ prompt                    ┃
   ┃ .favorite_subject_system_… ┃ .college_plan_user_prompt ┃ .college_plan_system_prom… ┃ .favorite_subject_user_p… ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
   │ You are answering          │                           │ You are answering          │                           │
   │ questions as if you were a │ Do you plan to go to      │ questions as if you were a │ What is your favorite     │
   │ human. Do not break        │ college?                  │ human. Do not break        │ subject?                  │
   │ character. You are an      │                           │ character. You are an      │                           │
   │ agent with the following   │                           │ agent with the following   │                           │
   │ persona:                   │ No                        │ persona:                   │ Math                      │
   │ {'persona': 'You are a     │                           │ {'persona': 'You are a     │                           │
   │ high school student.',     │ Yes                       │ high school student.',     │ English                   │
   │ 'age': 15}                 │                           │ 'age': 15}                 │                           │
   │                            │                           │                            │ Social studies            │
   │                            │ Only 1 option may be      │                            │                           │
   │                            │ selected.                 │                            │ Science                   │
   │                            │ Please respond with just  │                            │                           │
   │                            │ your answer.              │                            │ Other                     │
   │                            │                           │                            │                           │
   │                            │                           │                            │                           │
   │                            │                           │                            │ Only 1 option may be      │
   │                            │                           │                            │ selected.                 │
   │                            │                           │                            │                           │
   │                            │                           │                            │ Respond only with a       │
   │                            │                           │                            │ string corresponding to   │
   │                            │                           │                            │ one of the options.       │
   └────────────────────────────┴───────────────────────────┴────────────────────────────┴───────────────────────────┘


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


Output (note that comments have been turned off in this example):

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ prompt                     ┃ prompt                    ┃ prompt                     ┃ prompt                    ┃
   ┃ .favorite_subject_system_… ┃ .college_plan_system_pro… ┃ .favorite_subject_user_pr… ┃ .college_plan_user_prompt ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
   │ You are answering          │ You are answering         │                            │                           │
   │ questions as if you were a │ questions as if you were  │ What is your favorite      │ Do you plan to go to      │
   │ human. Do not break        │ a human. Do not break     │ subject?                   │ college?                  │
   │ character. You are an      │ character. You are an     │                            │                           │
   │ agent with the following   │ agent with the following  │                            │                           │
   │ persona:                   │ persona:                  │ Math                       │ No                        │
   │ {'persona': 'You are a     │ {'persona': 'You are a    │                            │                           │
   │ high school student.',     │ high school student.',    │ English                    │ Yes                       │
   │ 'age': 15}                 │ 'age': 15}                │                            │                           │
   │                            │                           │ Social studies             │                           │
   │                            │                           │                            │ Only 1 option may be      │
   │                            │                           │ Science                    │ selected.                 │
   │                            │                           │                            │ Please respond with just  │
   │                            │                           │ Other                      │ your answer.              │
   │                            │                           │                            │                           │
   │                            │                           │                            │                           │
   │                            │                           │ Only 1 option may be       │                           │
   │                            │                           │ selected.                  │                           │
   │                            │                           │                            │                           │
   │                            │                           │ Respond only with a string │                           │
   │                            │                           │ corresponding to one of    │                           │
   │                            │                           │ the options.               │                           │
   └────────────────────────────┴───────────────────────────┴────────────────────────────┴───────────────────────────┘

