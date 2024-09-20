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


Showing prompts 
^^^^^^^^^^^^^^^

Before a survey is run, EDSL creates a `Jobs` object. 
You can see the prompts it will use by calling `prompts()` on it. 
For example:

.. code-block:: python

   from edsl import Survey, Agent, Model

   survey = Survey.example()
   agent = Agent(traits = {"persona": "School teacher"})
   model = Model() # default model

   job = survey.by(agent).by(model) # Creating a job for the example survey using the agent and the default model

   job.prompts().print(format="rich")


This will display the prompts that will be used when the survey is run:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ interview_index ┃ question_index ┃ user_prompt              ┃ scenario_index        ┃ system_prompt             ┃
   ┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
   │ 0               │ q0             │                          │  Scenario Attributes  │ You are answering         │
   │                 │                │ Do you like school?      │ ┏━━━━━━━━━━━┳━━━━━━━┓ │ questions as if you were  │
   │                 │                │                          │ ┃ Attribute ┃ Value ┃ │ a human. Do not break     │
   │                 │                │                          │ ┡━━━━━━━━━━━╇━━━━━━━┩ │ character. You are an     │
   │                 │                │ yes                      │ │ data      │ {}    │ │ agent with the following  │
   │                 │                │                          │ │ name      │ None  │ │ persona:                  │
   │                 │                │ no                       │ └───────────┴───────┘ │ {'persona': 'School       │
   │                 │                │                          │                       │ teacher'}                 │
   │                 │                │                          │                       │                           │
   │                 │                │ Only 1 option may be     │                       │                           │
   │                 │                │ selected.                │                       │                           │
   │                 │                │                          │                       │                           │
   │                 │                │ Respond only with a      │                       │                           │
   │                 │                │ string corresponding to  │                       │                           │
   │                 │                │ one of the options.      │                       │                           │
   │                 │                │                          │                       │                           │
   │                 │                │                          │                       │                           │
   │                 │                │ After the answer, you    │                       │                           │
   │                 │                │ can put a comment        │                       │                           │
   │                 │                │ explaining why you chose │                       │                           │
   │                 │                │ that option on the next  │                       │                           │
   │                 │                │ line.                    │                       │                           │
   ├─────────────────┼────────────────┼──────────────────────────┼───────────────────────┼───────────────────────────┤
   │ 0               │ q1             │                          │  Scenario Attributes  │ You are answering         │
   │                 │                │ Why not?                 │ ┏━━━━━━━━━━━┳━━━━━━━┓ │ questions as if you were  │
   │                 │                │                          │ ┃ Attribute ┃ Value ┃ │ a human. Do not break     │
   │                 │                │                          │ ┡━━━━━━━━━━━╇━━━━━━━┩ │ character. You are an     │
   │                 │                │ killer bees in cafeteria │ │ data      │ {}    │ │ agent with the following  │
   │                 │                │                          │ │ name      │ None  │ │ persona:                  │
   │                 │                │ other                    │ └───────────┴───────┘ │ {'persona': 'School       │
   │                 │                │                          │                       │ teacher'}                 │
   │                 │                │                          │                       │                           │
   │                 │                │ Only 1 option may be     │                       │                           │
   │                 │                │ selected.                │                       │                           │
   │                 │                │                          │                       │                           │
   │                 │                │ Respond only with a      │                       │                           │
   │                 │                │ string corresponding to  │                       │                           │
   │                 │                │ one of the options.      │                       │                           │
   │                 │                │                          │                       │                           │
   │                 │                │                          │                       │                           │
   │                 │                │ After the answer, you    │                       │                           │
   │                 │                │ can put a comment        │                       │                           │
   │                 │                │ explaining why you chose │                       │                           │
   │                 │                │ that option on the next  │                       │                           │
   │                 │                │ line.                    │                       │                           │
   ├─────────────────┼────────────────┼──────────────────────────┼───────────────────────┼───────────────────────────┤
   │ 0               │ q2             │                          │  Scenario Attributes  │ You are answering         │
   │                 │                │ Why?                     │ ┏━━━━━━━━━━━┳━━━━━━━┓ │ questions as if you were  │
   │                 │                │                          │ ┃ Attribute ┃ Value ┃ │ a human. Do not break     │
   │                 │                │                          │ ┡━━━━━━━━━━━╇━━━━━━━┩ │ character. You are an     │
   │                 │                │ **lack*** of killer bees │ │ data      │ {}    │ │ agent with the following  │
   │                 │                │ in cafeteria             │ │ name      │ None  │ │ persona:                  │
   │                 │                │                          │ └───────────┴───────┘ │ {'persona': 'School       │
   │                 │                │ other                    │                       │ teacher'}                 │
   │                 │                │                          │                       │                           │
   │                 │                │                          │                       │                           │
   │                 │                │ Only 1 option may be     │                       │                           │
   │                 │                │ selected.                │                       │                           │
   │                 │                │                          │                       │                           │
   │                 │                │ Respond only with a      │                       │                           │
   │                 │                │ string corresponding to  │                       │                           │
   │                 │                │ one of the options.      │                       │                           │
   │                 │                │                          │                       │                           │
   │                 │                │                          │                       │                           │
   │                 │                │ After the answer, you    │                       │                           │
   │                 │                │ can put a comment        │                       │                           │
   │                 │                │ explaining why you chose │                       │                           │
   │                 │                │ that option on the next  │                       │                           │
   │                 │                │ line.                    │                       │                           │
   └─────────────────┴────────────────┴──────────────────────────┴───────────────────────┴───────────────────────────┘


After we run the survey, we can verify the prompts that were used by inspecting the `prompt.*` fields of the results:

.. code-block:: python

   results = job.run() # This is equivalent to: results = survey.by(agent).by(model).run()

   # To select all the `prompt` columns at once:
   # results.select("prompt.*").print(format="rich") 

   # Or to specify the order in the table we can name them individually:
   (
      results.select(
         "q0_system_prompt", "q0_user_prompt",
         "q1_system_prompt", "q1_user_prompt",
         "q2_system_prompt", "q2_user_prompt"
      )
      .print(format="rich")
   )


Output:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
   ┃ prompt           ┃ prompt           ┃ prompt           ┃ prompt           ┃ prompt           ┃ prompt           ┃
   ┃ .q0_system_prom… ┃ .q0_user_prompt  ┃ .q1_system_prom… ┃ .q1_user_prompt  ┃ .q2_system_prom… ┃ .q2_user_prompt  ┃
   ┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
   │ You are          │                  │ You are          │                  │ You are          │                  │
   │ answering        │ Do you like      │ answering        │ Why not?         │ answering        │ Why?             │
   │ questions as if  │ school?          │ questions as if  │                  │ questions as if  │                  │
   │ you were a       │                  │ you were a       │                  │ you were a       │                  │
   │ human. Do not    │                  │ human. Do not    │ killer bees in   │ human. Do not    │ **lack*** of     │
   │ break character. │ yes              │ break character. │ cafeteria        │ break character. │ killer bees in   │
   │ You are an agent │                  │ You are an agent │                  │ You are an agent │ cafeteria        │
   │ with the         │ no               │ with the         │ other            │ with the         │                  │
   │ following        │                  │ following        │                  │ following        │ other            │
   │ persona:         │                  │ persona:         │                  │ persona:         │                  │
   │ {'persona':      │ Only 1 option    │ {'persona':      │ Only 1 option    │ {'persona':      │                  │
   │ 'School          │ may be selected. │ 'School          │ may be selected. │ 'School          │ Only 1 option    │
   │ teacher'}        │                  │ teacher'}        │                  │ teacher'}        │ may be selected. │
   │                  │ Respond only     │                  │ Respond only     │                  │                  │
   │                  │ with a string    │                  │ with a string    │                  │ Respond only     │
   │                  │ corresponding to │                  │ corresponding to │                  │ with a string    │
   │                  │ one of the       │                  │ one of the       │                  │ corresponding to │
   │                  │ options.         │                  │ options.         │                  │ one of the       │
   │                  │                  │                  │                  │                  │ options.         │
   │                  │                  │                  │                  │                  │                  │
   │                  │ After the        │                  │ After the        │                  │                  │
   │                  │ answer, you can  │                  │ answer, you can  │                  │ After the        │
   │                  │ put a comment    │                  │ put a comment    │                  │ answer, you can  │
   │                  │ explaining why   │                  │ explaining why   │                  │ put a comment    │
   │                  │ you chose that   │                  │ you chose that   │                  │ explaining why   │
   │                  │ option on the    │                  │ option on the    │                  │ you chose that   │
   │                  │ next line.       │                  │ next line.       │                  │ option on the    │
   │                  │                  │                  │                  │                  │ next line.       │
   └──────────────────┴──────────────────┴──────────────────┴──────────────────┴──────────────────┴──────────────────┘

