.. _prompts:

Prompts
=======

Overview
--------

Prompts are texts that are sent to a language model in order to guide it on how to generate responses to questions.
Agent instructions are contained in a `system_prompt` and question instructions are contained in a `user_prompt`.
These texts can include questions, instructions or any other text to be displayed to the language model.

Typically, prompts are created using the `Prompt` class, a subclass of the `PromptBase` class which is an abstract class that defines the basic structure of a prompt.

Default prompts are provided in the `edsl.prompts.library` module. 
These prompts can be used as is or customized to suit specific requirements by creating new classes that inherit from the `Prompt` class.

Note: If an `Agent` is not used with a survey the `system_prompt` base text is not sent to the model.


Show prompts 
------------

Before a survey is run, EDSL creates a `Jobs` object. 
You can inspect the prompts it will use by calling `show_prompts()` on the object, or access the prompts as a dataset by calling `prompts()`.

For example, here we create a simple survey of two questions and show the prompts that will be used when the survey is run:

.. code-block:: python

   from edsl import QuestionMultipleChoice, QuestionFreeText, Survey, Agent, Model

   q1 = QuestionMultipleChoice(
      question_name = "commute",
      question_text = "Which mode of transportation do you most often use to commute to work?", 
      question_options = ["Car", "Public transportation", "Bike", "Walk", "Work from home", "Other"]
   )

   q2 = QuestionFreeText(
      question_name = "improvements",
      question_text = "What improvements would you like to see in your options for commuting to work?"
   )

   survey = Survey(questions = [q1, q2])
                  
   agent = Agent(
      traits = {"persona": "School teacher"}
   )

   model = Model("gemini-1.5-flash")

   job.show_prompts().print(format="rich")


This will display the prompts that will be used when the survey is run, together with the agent, model and estimated cost information:

.. code-block:: text

   ┏━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
   ┃ user_prompt ┃ system_pro… ┃ interview_… ┃ question_n… ┃ scenario_in… ┃ agent_index ┃ model       ┃ estimated_c… ┃
   ┡━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━━┩
   │             │ You are     │ 0           │ commute     │ 0            │ 0           │ gemini-1.5… │ 0.0          │
   │ Which mode  │ answering   │             │             │              │             │             │              │
   │ of          │ questions   │             │             │              │             │             │              │
   │ transporta… │ as if you   │             │             │              │             │             │              │
   │ do you most │ were a      │             │             │              │             │             │              │
   │ often use   │ human. Do   │             │             │              │             │             │              │
   │ to commute  │ not break   │             │             │              │             │             │              │
   │ to work?    │ character.  │             │             │              │             │             │              │
   │             │ You are an  │             │             │              │             │             │              │
   │             │ agent with  │             │             │              │             │             │              │
   │ Car         │ the         │             │             │              │             │             │              │
   │             │ following   │             │             │              │             │             │              │
   │ Public      │ persona:    │             │             │              │             │             │              │
   │ transporta… │ {'persona': │             │             │              │             │             │              │
   │             │ 'School     │             │             │              │             │             │              │
   │ Bike        │ teacher'}   │             │             │              │             │             │              │
   │             │             │             │             │              │             │             │              │
   │ Walk        │             │             │             │              │             │             │              │
   │             │             │             │             │              │             │             │              │
   │ Work from   │             │             │             │              │             │             │              │
   │ home        │             │             │             │              │             │             │              │
   │             │             │             │             │              │             │             │              │
   │ Other       │             │             │             │              │             │             │              │
   │             │             │             │             │              │             │             │              │
   │             │             │             │             │              │             │             │              │
   │ Only 1      │             │             │             │              │             │             │              │
   │ option may  │             │             │             │              │             │             │              │
   │ be          │             │             │             │              │             │             │              │
   │ selected.   │             │             │             │              │             │             │              │
   │             │             │             │             │              │             │             │              │
   │ Respond     │             │             │             │              │             │             │              │
   │ only with a │             │             │             │              │             │             │              │
   │ string      │             │             │             │              │             │             │              │
   │ correspond… │             │             │             │              │             │             │              │
   │ to one of   │             │             │             │              │             │             │              │
   │ the         │             │             │             │              │             │             │              │
   │ options.    │             │             │             │              │             │             │              │
   │             │             │             │             │              │             │             │              │
   │             │             │             │             │              │             │             │              │
   │ After the   │             │             │             │              │             │             │              │
   │ answer, you │             │             │             │              │             │             │              │
   │ can put a   │             │             │             │              │             │             │              │
   │ comment     │             │             │             │              │             │             │              │
   │ explaining  │             │             │             │              │             │             │              │
   │ why you     │             │             │             │              │             │             │              │
   │ chose that  │             │             │             │              │             │             │              │
   │ option on   │             │             │             │              │             │             │              │
   │ the next    │             │             │             │              │             │             │              │
   │ line.       │             │             │             │              │             │             │              │
   ├─────────────┼─────────────┼─────────────┼─────────────┼──────────────┼─────────────┼─────────────┼──────────────┤
   │ What        │ You are     │ 0           │ improvemen… │ 0            │ 0           │ gemini-1.5… │ 0.0          │
   │ improvemen… │ answering   │             │             │              │             │             │              │
   │ would you   │ questions   │             │             │              │             │             │              │
   │ like to see │ as if you   │             │             │              │             │             │              │
   │ in your     │ were a      │             │             │              │             │             │              │
   │ options for │ human. Do   │             │             │              │             │             │              │
   │ commuting   │ not break   │             │             │              │             │             │              │
   │ to work?    │ character.  │             │             │              │             │             │              │
   │             │ You are an  │             │             │              │             │             │              │
   │             │ agent with  │             │             │              │             │             │              │
   │             │ the         │             │             │              │             │             │              │
   │             │ following   │             │             │              │             │             │              │
   │             │ persona:    │             │             │              │             │             │              │
   │             │ {'persona': │             │             │              │             │             │              │
   │             │ 'School     │             │             │              │             │             │              │
   │             │ teacher'}   │             │             │              │             │             │              │
   └─────────────┴─────────────┴─────────────┴─────────────┴──────────────┴─────────────┴─────────────┴──────────────┘


We can see that the prompts for the first question are:

- `system_prompt`: "You are answering questions as if you were a human. Do not break character. You are an agent with the following persona: {'persona': 'School teacher'}"
- `user_prompt`: "Which mode of transportation do you most often use to commute to work? Only 1 option may be selected. Respond only with a string corresponding to one of the options. After the answer, you can put a comment explaining why you chose that option on the next line."

And the prompts for the second question are:

- `system_prompt`: "You are answering questions as if you were a human. Do not break character. You are an agent with the following persona: {'persona': 'School teacher'}"
- `user_prompt`: "What improvements would you like to see in your options for commuting to work? Respond only with a string. After the answer, you can put a comment explaining why you chose that option on the next line."

This is equivalent to running `job.prompts().print(format="rich")`.

To access the prompts as a dataset:

.. code-block:: python

   prompts = job.prompts()
   prompts


Output:

.. code-block:: text

   [
      {
         "user_prompt": [
               "\nWhich mode of transportation do you most often use to commute to work?\n\n    \nCar\n    \nPublic transportation\n    \nBike\n    \nWalk\n    \nWork from home\n    \nOther\n    \n\nOnly 1 option may be selected.\n\nRespond only with a string corresponding to one of the options.\n\n\nAfter the answer, you can put a comment explaining why you chose that option on the next line.",
               "What improvements would you like to see in your options for commuting to work?"
         ]
      },
      {
         "system_prompt": [
               "You are answering questions as if you were a human. Do not break character. You are an agent with the following persona:\n{'persona': 'School teacher'}",
               "You are answering questions as if you were a human. Do not break character. You are an agent with the following persona:\n{'persona': 'School teacher'}"
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
               "commute",
               "improvements"
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
               "gemini-1.5-flash",
               "gemini-1.5-flash"
         ]
      },
      {
         "estimated_cost": [
               0.0,
               0.0
         ]
      }
   ]


Inspecting prompts after running a survey
-----------------------------------------

After a survey is run, you can inspect the prompts that were used by inspecting the `prompt.*` fields of the results.

For example, here we run the survey from above and inspect the prompts that were used:

.. code-block:: python

   results = job.run() 
   

This is equivalent to running `results = survey.by(agent).by(model).run()`.

To select all the `prompt` columns at once:

.. code-block:: python

   results.select("prompt.*").print(format="rich") 


Output:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ prompt                     ┃ prompt                    ┃ prompt                     ┃ prompt                    ┃
   ┃ .improvements_user_prompt  ┃ .commute_system_prompt    ┃ .commute_user_prompt       ┃ .improvements_system_pro… ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
   │ What improvements would    │ You are answering         │                            │ You are answering         │
   │ you like to see in your    │ questions as if you were  │ Which mode of              │ questions as if you were  │
   │ options for commuting to   │ a human. Do not break     │ transportation do you most │ a human. Do not break     │
   │ work?                      │ character. You are an     │ often use to commute to    │ character. You are an     │
   │                            │ agent with the following  │ work?                      │ agent with the following  │
   │                            │ persona:                  │                            │ persona:                  │
   │                            │ {'persona': 'School       │                            │ {'persona': 'School       │
   │                            │ teacher'}                 │ Car                        │ teacher'}                 │
   │                            │                           │                            │                           │
   │                            │                           │ Public transportation      │                           │
   │                            │                           │                            │                           │
   │                            │                           │ Bike                       │                           │
   │                            │                           │                            │                           │
   │                            │                           │ Walk                       │                           │
   │                            │                           │                            │                           │
   │                            │                           │ Work from home             │                           │
   │                            │                           │                            │                           │
   │                            │                           │ Other                      │                           │
   │                            │                           │                            │                           │
   │                            │                           │                            │                           │
   │                            │                           │ Only 1 option may be       │                           │
   │                            │                           │ selected.                  │                           │
   │                            │                           │                            │                           │
   │                            │                           │ Respond only with a string │                           │
   │                            │                           │ corresponding to one of    │                           │
   │                            │                           │ the options.               │                           │
   │                            │                           │                            │                           │
   │                            │                           │                            │                           │
   │                            │                           │ After the answer, you can  │                           │
   │                            │                           │ put a comment explaining   │                           │
   │                            │                           │ why you chose that option  │                           │
   │                            │                           │ on the next line.          │                           │
   └────────────────────────────┴───────────────────────────┴────────────────────────────┴───────────────────────────┘


Or to specify the order in the table we can name them individually:

.. code-block:: python

   (
      results.select(
         "commute_system_prompt",
         "improvements_system_prompt",
         "commute_user_prompt",
         "improvements_user_prompt"
      )
      .print(format="rich")
   )


Output:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ prompt                     ┃ prompt                    ┃ prompt                     ┃ prompt                    ┃
   ┃ .commute_system_prompt     ┃ .improvements_system_pro… ┃ .commute_user_prompt       ┃ .improvements_user_prompt ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
   │ You are answering          │ You are answering         │                            │ What improvements would   │
   │ questions as if you were a │ questions as if you were  │ Which mode of              │ you like to see in your   │
   │ human. Do not break        │ a human. Do not break     │ transportation do you most │ options for commuting to  │
   │ character. You are an      │ character. You are an     │ often use to commute to    │ work?                     │
   │ agent with the following   │ agent with the following  │ work?                      │                           │
   │ persona:                   │ persona:                  │                            │                           │
   │ {'persona': 'School        │ {'persona': 'School       │                            │                           │
   │ teacher'}                  │ teacher'}                 │ Car                        │                           │
   │                            │                           │                            │                           │
   │                            │                           │ Public transportation      │                           │
   │                            │                           │                            │                           │
   │                            │                           │ Bike                       │                           │
   │                            │                           │                            │                           │
   │                            │                           │ Walk                       │                           │
   │                            │                           │                            │                           │
   │                            │                           │ Work from home             │                           │
   │                            │                           │                            │                           │
   │                            │                           │ Other                      │                           │
   │                            │                           │                            │                           │
   │                            │                           │                            │                           │
   │                            │                           │ Only 1 option may be       │                           │
   │                            │                           │ selected.                  │                           │
   │                            │                           │                            │                           │
   │                            │                           │ Respond only with a string │                           │
   │                            │                           │ corresponding to one of    │                           │
   │                            │                           │ the options.               │                           │
   │                            │                           │                            │                           │
   │                            │                           │                            │                           │
   │                            │                           │ After the answer, you can  │                           │
   │                            │                           │ put a comment explaining   │                           │
   │                            │                           │ why you chose that option  │                           │
   │                            │                           │ on the next line.          │                           │
   └────────────────────────────┴───────────────────────────┴────────────────────────────┴───────────────────────────┘

