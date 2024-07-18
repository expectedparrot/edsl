.. _prompts:

Prompts
=======

Overview
--------
Prompts are texts that are sent to a language model in order to guide it on how to generate responses to questions.
They consist of `agent instructions` and `question instructions`, and can include questions, instructions or any other text to be displayed to the language model.

Typically, prompts are created using the `Prompt` class, a subclass of the `PromptBase` class which is an abstract class that defines the basic structure of a prompt.

Default prompts are provided in the `edsl.prompts.library` module. 
These prompts can be used as is or customized to suit specific requirements by creating new classes that inherit from the `Prompt` class.


Default prompts 
^^^^^^^^^^^^^^^
The `edsl.prompts.library` module contains default prompts for agent instructions and question instructions (shown below).
If custom prompts are not specified, the default prompts used to generate results can be readily inspected by selecting the **prompt** columns in the results.
For example, we can inspect the prompts for the sample results generated in the `edsl.results` section:

.. code-block:: python

   results.select("prompt.*").print(pretty_labels={
      "prompt.tomorrow_user_prompt": "Tomorrow: question instruction",
      "prompt.tomorrow_system_prompt": "Tomorrow: agent instruction",
      "prompt.yesterday_user_prompt": "Yesterday: question instruction",
      "prompt.yesterday_system_prompt": "Yesterday: agent instruction"
   })

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ Yesterday: question        ┃ Tomorrow: agent           ┃ Yesterday: agent           ┃ Tomorrow: question        ┃
   ┃ instruction                ┃ instruction               ┃ instruction                ┃ instruction               ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
   │ {'text': 'You are being    │ {'text': "You are         │ {'text': "You are          │ {'text': 'You are being   │
   │ asked the following        │ answering questions as if │ answering questions as if  │ asked the following       │
   │ question: How did you feel │ you were a human. Do not  │ you were a human. Do not   │ question: How do you      │
   │ yesterday morning?\nThe    │ break character. You are  │ break character. You are   │ expect to feel tomorrow   │
   │ options are\n\n0:          │ an agent with the         │ an agent with the          │ morning?\nReturn a valid  │
   │ Good\n\n1: OK\n\n2:        │ following                 │ following                  │ JSON formatted like       │
   │ Terrible\n\nReturn a valid │ persona:\n{'status':      │ persona:\n{'status':       │ this:\n{"answer": "<put   │
   │ JSON formatted like this,  │ 'happy'}", 'class_name':  │ 'happy'}", 'class_name':   │ free text answer          │
   │ selecting only the number  │ 'AgentInstructionLlama'}  │ 'AgentInstructionLlama'}   │ here>"}', 'class_name':   │
   │ of the option:\n{"answer": │                           │                            │ 'FreeText'}               │
   │ <put answer code here>,    │                           │                            │                           │
   │ "comment": "<put           │                           │                            │                           │
   │ explanation here>"}\nOnly  │                           │                            │                           │
   │ 1 option may be            │                           │                            │                           │
   │ selected.', 'class_name':  │                           │                            │                           │
   │ 'MultipleChoiceTurbo'}     │                           │                            │                           │
   ├────────────────────────────┼───────────────────────────┼────────────────────────────┼───────────────────────────┤
   
   ...


Showing prompts 
^^^^^^^^^^^^^^^
Before you run a survey, EDSL creates a `Jobs` object. You can see the prompts it will use by calling `prompts()` on the `Jobs` object. 
For example:

.. code-block:: python

   from edsl import Model, Survey
   j = Survey.example().by(Model())
   j.prompts().print()

This will display the prompts that will be used in the survey:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ interview_index ┃ question_index ┃ user_prompt              ┃ scenario_index         ┃ system_prompt            ┃
   ┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━┩
   │ 0               │ q0             │ You are being asked the  │  Scenario Attributes   │ You are answering        │
   │                 │                │ following question: Do   │ ┏━━━━━━━━━━━━┳━━━━━━━┓ │ questions as if you were │
   │                 │                │ you like school?         │ ┃ Attribute  ┃ Value ┃ │ a human. Do not break    │
   │                 │                │ The options are          │ ┡━━━━━━━━━━━━╇━━━━━━━┩ │ character. You are an    │
   │                 │                │                          │ │ data       │ {}    │ │ agent with the following │
   │                 │                │ 0: yes                   │ │ name       │ None  │ │ persona:                 │
   │                 │                │                          │ │ _has_image │ False │ │ {}                       │
   │                 │                │ 1: no                    │ └────────────┴───────┘ │                          │
   │                 │                │                          │                        │                          │
   │                 │                │ Return a valid JSON      │                        │                          │
   │                 │                │ formatted like this,     │                        │                          │
   │                 │                │ selecting only the       │                        │                          │
   │                 │                │ number of the option:    │                        │                          │
   │                 │                │ {"answer": <put answer   │                        │                          │
   │                 │                │ code here>, "comment":   │                        │                          │
   │                 │                │ "<put explanation        │                        │                          │
   │                 │                │ here>"}                  │                        │                          │
   │                 │                │ Only 1 option may be     │                        │                          │
   │                 │                │ selected.                │                        │                          │
   ├─────────────────┼────────────────┼──────────────────────────┼────────────────────────┼──────────────────────────┤
   │ 0               │ q1             │ You are being asked the  │  Scenario Attributes   │ You are answering        │
   │                 │                │ following question: Why  │ ┏━━━━━━━━━━━━┳━━━━━━━┓ │ questions as if you were │
   │                 │                │ not?                     │ ┃ Attribute  ┃ Value ┃ │ a human. Do not break    │
   │                 │                │ The options are          │ ┡━━━━━━━━━━━━╇━━━━━━━┩ │ character. You are an    │
   │                 │                │                          │ │ data       │ {}    │ │ agent with the following │
   │                 │                │ 0: killer bees in        │ │ name       │ None  │ │ persona:                 │
   │                 │                │ cafeteria                │ │ _has_image │ False │ │ {}                       │
   │                 │                │                          │ └────────────┴───────┘ │                          │
   │                 │                │ 1: other                 │                        │                          │
   │                 │                │                          │                        │                          │
   │                 │                │ Return a valid JSON      │                        │                          │
   │                 │                │ formatted like this,     │                        │                          │
   │                 │                │ selecting only the       │                        │                          │
   │                 │                │ number of the option:    │                        │                          │
   │                 │                │ {"answer": <put answer   │                        │                          │
   │                 │                │ code here>, "comment":   │                        │                          │
   │                 │                │ "<put explanation        │                        │                          │
   │                 │                │ here>"}                  │                        │                          │
   │                 │                │ Only 1 option may be     │                        │                          │
   │                 │                │ selected.                │                        │                          │
   ├─────────────────┼────────────────┼──────────────────────────┼────────────────────────┼──────────────────────────┤
   │ 0               │ q2             │ You are being asked the  │  Scenario Attributes   │ You are answering        │
   │                 │                │ following question: Why? │ ┏━━━━━━━━━━━━┳━━━━━━━┓ │ questions as if you were │
   │                 │                │ The options are          │ ┃ Attribute  ┃ Value ┃ │ a human. Do not break    │
   │                 │                │                          │ ┡━━━━━━━━━━━━╇━━━━━━━┩ │ character. You are an    │
   │                 │                │ 0: **lack*** of killer   │ │ data       │ {}    │ │ agent with the following │
   │                 │                │ bees in cafeteria        │ │ name       │ None  │ │ persona:                 │
   │                 │                │                          │ │ _has_image │ False │ │ {}                       │
   │                 │                │ 1: other                 │ └────────────┴───────┘ │                          │
   │                 │                │                          │                        │                          │
   │                 │                │ Return a valid JSON      │                        │                          │
   │                 │                │ formatted like this,     │                        │                          │
   │                 │                │ selecting only the       │                        │                          │
   │                 │                │ number of the option:    │                        │                          │
   │                 │                │ {"answer": <put answer   │                        │                          │
   │                 │                │ code here>, "comment":   │                        │                          │
   │                 │                │ "<put explanation        │                        │                          │
   │                 │                │ here>"}                  │                        │                          │
   │                 │                │ Only 1 option may be     │                        │                          │
   │                 │                │ selected.                │                        │                          │
   └─────────────────┴────────────────┴──────────────────────────┴────────────────────────┴──────────────────────────┘


Agent instructions
^^^^^^^^^^^^^^^^^^
The `AgentInstruction` class provides guidance to a language model on how an agent should be represented. 
As shown in the example above, the default agent instructions are:

.. code-block:: python

   class AgentInstruction(PromptBase):
      \"\"\"Agent instructions for a human agent.\"\"\"

      model = LanguageModelType.GPT_3_5_Turbo.value
      component_type = ComponentTypes.AGENT_INSTRUCTIONS
      default_instructions = textwrap.dedent(
         \"\"\"\
         You are playing the role of a human answering survey questions.
         Do not break character.
         \"\"\"
      )


Question instructions
^^^^^^^^^^^^^^^^^^^^^
The `QuestionInstruction` class provides guidance to a language model on how a question should be answered.
As shown in the example above, the following question instructions are:

.. code-block:: python

   class QuestionInstruction(PromptBase):
      \"\"\"Question instructions for a multiple choice question.\"\"\"

      model = LanguageModelType.GPT_3_5_Turbo.value
      component_type = ComponentTypes.QUESTION_INSTRUCTIONS
      default_instructions = textwrap.dedent(
         \"\"\"\
         You are answering a multiple choice question.
         \"\"\"
      )


Customizing prompts
^^^^^^^^^^^^^^^^^^^
We can customize prompts by creating new classes that inherit from the `Prompt` class.
For example, consider the following custom agent instructions:

.. code-block:: python

   applicable_prompts = get_classes(
      component_type="agent_instructions",
      model=self.model.model,
   )



Prompt class
------------

.. automodule:: edsl.prompts.Prompt
   :members:
   :undoc-members:
   :show-inheritance:


Agent Instructions
------------------

.. automodule:: edsl.prompts.library.agent_instructions
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: edsl.prompts.library.agent_persona
   :members:
   :undoc-members:
   :show-inheritance:


Question Instructions
---------------------

.. automodule:: edsl.prompts.library.question_multiple_choice
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: edsl.prompts.library.question_numerical
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: edsl.prompts.library.question_budget
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: edsl.prompts.library.question_freetext
   :members:
   :undoc-members:
   :show-inheritance:


QuestionInstructionBase class
-----------------------------

.. automodule:: edsl.prompts.QuestionInstructionBase
   :members:
   :undoc-members:
   :show-inheritance: