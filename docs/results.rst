.. _results:

Results
=======
A `Results` object is the result of running a survey. 
It is a list of individual `Result` objects, each of which represents a response to a `Survey` for each combination of `Agent`, `Model` and `Scenario` objects that were used with the survey.
For example, the `Results` of a survey administered to 2 agents and 2 language models with no question scenarios will contain 4 individual `Result` objects.
If the survey questions are parameterized with 2 scenarios then the survey `Results` will include 8 `Result` objects.

A `Results` object is not typically instantiated directly, but is returned by calling the `run()` method of a survey after any agents, language models and scenarios are added to it. 
To inspect the form of an example `Results` we can call the `example()` method (it is long -- we show it at the end of this page):

.. code-block:: python

   from edsl import Results

   example_results = Results.example()


We can see the number of `Result` objects created by inspecting the length of the `Results`:

.. code-block:: python

   len(example_results)


Output:

.. code-block:: text

   4


We can verify that object types:

.. code-block:: python

   type(example_results)


Output

.. code-block:: text

   edsl.results.Results.Results


And the 4 `Result` objects:

.. code-block:: python

   type(example_results[0])


Output:

.. code-block:: text

   edsl.results.Results.Result


**Note:** You must have API keys for language models in order to generate results. 
Please see the :ref:`api_keys` section for instructions on activating :ref:`remote_inference` from your :ref:`coop` account or storing your own API keys.

For purposes of demonstrating how to unpack and interact with results, we'll use the following code to generate results for a simple survey.
Note that specifying agent traits, scenarios (question parameter values) and language models is optional, and we include those steps here for illustrative purposes:

.. code-block:: python

   # Create questions
   from edsl import QuestionLinearScale, QuestionFreeText, QuestionMultipleChoice

   q1 = QuestionLinearScale(
      question_name = "important",
      question_text = "On a scale from 1 to 5, how important to you is {{ topic }}?",
      question_options = [0, 1, 2, 3, 4, 5],
      option_labels = {0:"Not at all", 5:"Very much"}
   )

   q2 = QuestionFreeText(
      question_name = "opinions",
      question_text = "What are your opinions on {{ topic }}?"
   )

   q3 = QuestionMultipleChoice(
      question_name = "read",
      question_text = "Have you read any books about {{ topic }}?",
      question_options = ["Yes", "No", "I do not know"]
   )

   # Optionally parameterize the questions with scenarios
   from edsl import ScenarioList

   scenarios = ScenarioList.from_list("topic", ["climate change", "data privacy"])

   # Optionally create agents with traits
   from edsl import AgentList, Agent

   agents = AgentList(
      Agent(traits = {"persona": p}) for p in ["student", "celebrity"]
   )

   # Optionally specify language models
   from edsl import ModelList, Model

   models = ModelList(
      Model(m) for m in ["claude-3-5-sonnet-20240620", "gpt-4o"]
   )

   # Create a survey with the questions
   from edsl import Survey

   survey = Survey([q1, q2, q3])

   # Run the survey with the scenarios, agents and models
   results = survey.by(scenarios).by(agents).by(models).run()


For more details on each of the above steps, please see the relevant sections of the docs.


Result objects 
^^^^^^^^^^^^^^
We can check the number of `Result` objects created by inspecting the length of the `Results`:

.. code-block:: python

   len(results)

This will count 2 (scenarios) x 2 (agents) x 2 (models) = 8 `Result` objects:

.. code-block:: text

   8


Generating multiple results
^^^^^^^^^^^^^^^^^^^^^^^^^^^
If we want to generate multiple results for a survey--i.e., more than 1 result for each combination of `Agent`, `Model` and `Scenario` objects used--we can pass the desired number of iterations when calling the `run()` method.
For example, the following code will generate 3 results for our survey (n=3):

.. code-block:: python

   results = survey.by(scenarios).by(agents).by(models).run(n=3)


We can verify that the number of `Result` objects created is now 24 = 3 iterations x 2 scenarios x 2 agents x 2 models:

.. code-block:: python

   len(results)

.. code-block:: text

   24


We can readily inspect a result:

.. code-block:: python

   results[0]


.. code-block:: text
      
   {
      "agent": {
         "traits": {
               "persona": "student"
         },
         "edsl_version": "0.1.33.dev1",
         "edsl_class_name": "Agent"
      },
      "scenario": {
         "topic": "climate change",
         "edsl_version": "0.1.33.dev1",
         "edsl_class_name": "Scenario"
      },
      "model": {
         "model": "claude-3-5-sonnet-20240620",
         "parameters": {
               "temperature": 0.5,
               "max_tokens": 1000,
               "top_p": 1,
               "frequency_penalty": 0,
               "presence_penalty": 0,
               "logprobs": false,
               "top_logprobs": 3
         },
         "edsl_version": "0.1.33.dev1",
         "edsl_class_name": "LanguageModel"
      },
      "iteration": 0,
      "answer": {
         "important": 4,
         "opinions": "As a student, I'm still learning about climate change and forming my views on it. From what I've studied so far in my science classes, the scientific consensus seems to be that climate change is a real phenomenon and human activities are contributing to it. I find the topic really interesting and important to understand. I try to stay up to date by reading articles and reports from reputable scientific sources. At the same time, I know there's still a lot of debate around the specific impacts and best solutions. I'm eager to continue learning more as I progress in my studies.",
         "read": "Yes"
      },
      "prompt": {
         "important_user_prompt": {
               "text": "On a scale from 1 to 5, how important to you is climate change?\n\n0 : Not at all\n\n1 : \n\n2 : \n\n3 : \n\n4 : \n\n5 : Very much\n\nOnly 1 option may be selected.\n\nRespond only with the code corresponding to one of the options. E.g., \"1\" or \"5\" by itself.\n\nAfter the answer, you can put a comment explaining why you chose that option on the next line.",
               "class_name": "Prompt"
         },
         "important_system_prompt": {
               "text": "You are answering questions as if you were a human. Do not break character. You are an agent with the following persona:\n{'persona': 'student'}",
               "class_name": "AgentInstruction"
         },
         "opinions_user_prompt": {
               "text": "What are your opinions on climate change?",
               "class_name": "Prompt"
         },
         "opinions_system_prompt": {
               "text": "You are answering questions as if you were a human. Do not break character. You are an agent with the following persona:\n{'persona': 'student'}",
               "class_name": "AgentInstruction"
         },
         "read_user_prompt": {
               "text": "\nHave you read any books about climate change?\n\n    \nYes\n    \nNo\n    \nI do not know\n    \n\nOnly 1 option may be selected.\n\nRespond only with a string corresponding to one of the options.\n\n\nAfter the answer, you can put a comment explaining why you chose that option on the next line.",
               "class_name": "Prompt"
         },
         "read_system_prompt": {
               "text": "You are answering questions as if you were a human. Do not break character. You are an agent with the following persona:\n{'persona': 'student'}",
               "class_name": "AgentInstruction"
         }
      },
      "raw_model_response": {
         "important_raw_model_response": {
               "id": "msg_01HGaPNDtj6fkCLdbdy3h4HA",
               "content": [
                  {
                     "text": "4\n\nAs a student, I'm quite concerned about climate change and its long-term impacts on our planet and future generations. It's a major issue we learn about in school, and I feel it's important to be informed and take action where we can.",
                     "type": "text"
                  }
               ],
               "model": "claude-3-5-sonnet-20240620",
               "role": "assistant",
               "stop_reason": "end_turn",
               "stop_sequence": null,
               "type": "message",
               "usage": {
                  "input_tokens": 152,
                  "output_tokens": 57
               }
         },
         "important_cost": 0.001310994813023199,
         "important_one_usd_buys": 762.779524423873,
         "opinions_raw_model_response": {
               "id": "msg_017mQNAmbkvzuLLtpe7HzhiS",
               "content": [
                  {
                     "text": "As a student, I'm still learning about climate change and forming my views on it. From what I've studied so far in my science classes, the scientific consensus seems to be that climate change is a real phenomenon and human activities are contributing to it. I find the topic really interesting and important to understand. I try to stay up to date by reading articles and reports from reputable scientific sources. At the same time, I know there's still a lot of debate around the specific impacts and best solutions. I'm eager to continue learning more as I progress in my studies.",
                     "type": "text"
                  }
               ],
               "model": "claude-3-5-sonnet-20240620",
               "role": "assistant",
               "stop_reason": "end_turn",
               "stop_sequence": null,
               "type": "message",
               "usage": {
                  "input_tokens": 49,
                  "output_tokens": 119
               }
         },
         "opinions_cost": 0.0019319907810452126,
         "opinions_one_usd_buys": 517.6008135292432,
         "read_raw_model_response": {
               "id": "msg_01VwAiiNMiwTZQ6Q4jU5hPof",
               "content": [
                  {
                     "text": "Yes\n\nAs a student, I've likely had to read at least one book about climate change for a science or environmental studies class. It's a major topic covered in many curricula these days.",
                     "type": "text"
                  }
               ],
               "model": "claude-3-5-sonnet-20240620",
               "role": "assistant",
               "stop_reason": "end_turn",
               "stop_sequence": null,
               "type": "message",
               "usage": {
                  "input_tokens": 114,
                  "output_tokens": 43
               }
         },
         "read_cost": 0.000986996091017493,
         "read_one_usd_buys": 1013.1752385859008
      },
      "question_to_attributes": {
         "important": {
               "question_text": "On a scale from 1 to 5, how important to you is {{ topic }}?",
               "question_type": "linear_scale",
               "question_options": [
                  0,
                  1,
                  2,
                  3,
                  4,
                  5
               ]
         },
         "opinions": {
               "question_text": "What are your opinions on {{ topic }}?",
               "question_type": "free_text",
               "question_options": null
         },
         "read": {
               "question_text": "Have you read any books about {{ topic }}?",
               "question_type": "multiple_choice",
               "question_options": [
                  "Yes",
                  "No",
                  "I do not know"
               ]
         }
      },
      "generated_tokens": {
         "important_generated_tokens": "4\n\nAs a student, I'm quite concerned about climate change and its long-term impacts on our planet and future generations. It's a major issue we learn about in school, and I feel it's important to be informed and take action where we can.",
         "opinions_generated_tokens": "As a student, I'm still learning about climate change and forming my views on it. From what I've studied so far in my science classes, the scientific consensus seems to be that climate change is a real phenomenon and human activities are contributing to it. I find the topic really interesting and important to understand. I try to stay up to date by reading articles and reports from reputable scientific sources. At the same time, I know there's still a lot of debate around the specific impacts and best solutions. I'm eager to continue learning more as I progress in my studies.",
         "read_generated_tokens": "Yes\n\nAs a student, I've likely had to read at least one book about climate change for a science or environmental studies class. It's a major topic covered in many curricula these days."
      }
   }


We can use the `rich_print` method to display the `Result` object in a more readable format:

.. code-block:: python

   results[0].rich_print()


.. code-block:: text

                                                         Result                                                       
   ┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ Attribute              ┃ Value                                                                                  ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
   │ agent                  │                                    Agent Attributes                                    │
   │                        │ ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
   │                        │ ┃ Attribute                   ┃ Value                                                ┃ │
   │                        │ ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩ │
   │                        │ │ _name                       │ None                                                 │ │
   │                        │ │ _traits                     │ {'persona': 'student'}                               │ │
   │                        │ │ _codebook                   │ {}                                                   │ │
   │                        │ │ _instruction                │ 'You are answering questions as if you were a human. │ │
   │                        │ │                             │ Do not break character.'                             │ │
   │                        │ │ set_instructions            │ False                                                │ │
   │                        │ │ dynamic_traits_function     │ None                                                 │ │
   │                        │ │ has_dynamic_traits_function │ False                                                │ │
   │                        │ │ current_question            │ Question('multiple_choice', question_name =          │ │
   │                        │ │                             │ """read""", question_text = """Have you read any     │ │
   │                        │ │                             │ books about {{ topic }}?""", question_options =      │ │
   │                        │ │                             │ ['Yes', 'No', 'I do not know'])                      │ │
   │                        │ └─────────────────────────────┴──────────────────────────────────────────────────────┘ │
   │ scenario               │             Scenario Attributes                                                        │
   │                        │ ┏━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓                                            │
   │                        │ ┃ Attribute ┃ Value                       ┃                                            │
   │                        │ ┡━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩                                            │
   │                        │ │ data      │ {'topic': 'climate change'} │                                            │
   │                        │ │ name      │ None                        │                                            │
   │                        │ └───────────┴─────────────────────────────┘                                            │
   │ model                  │                                     Language Model                                     │
   │                        │ ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
   │                        │ ┃ Attribute                   ┃ Value                                                ┃ │
   │                        │ ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩ │
   │                        │ │ model                       │ 'claude-3-5-sonnet-20240620'                         │ │
   │                        │ │ parameters                  │ {'temperature': 0.5, 'max_tokens': 1000, 'top_p': 1, │ │
   │                        │ │                             │ 'frequency_penalty': 0, 'presence_penalty': 0,       │ │
   │                        │ │                             │ 'logprobs': False, 'top_logprobs': 3}                │ │
   │                        │ │ remote                      │ False                                                │ │
   │                        │ │ omit_system_prompt_if_empty │ True                                                 │ │
   │                        │ │ temperature                 │ 0.5                                                  │ │
   │                        │ │ max_tokens                  │ 1000                                                 │ │
   │                        │ │ top_p                       │ 1                                                    │ │
   │                        │ │ frequency_penalty           │ 0                                                    │ │
   │                        │ │ presence_penalty            │ 0                                                    │ │
   │                        │ │ logprobs                    │ False                                                │ │
   │                        │ │ top_logprobs                │ 3                                                    │ │
   │                        │ │ _LanguageModel__rate_limits │ {'rpm': 10000, 'tpm': 2000000}                       │ │
   │                        │ └─────────────────────────────┴──────────────────────────────────────────────────────┘ │
   │ iteration              │ 0                                                                                      │
   │ answer                 │ ┏━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
   │                        │ ┃ Attribute ┃ Value                                                                  ┃ │
   │                        │ ┡━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩ │
   │                        │ │ important │ 4                                                                      │ │
   │                        │ │ opinions  │ "As a student, I'm still learning about climate change and forming my  │ │
   │                        │ │           │ views on it. From what I've studied so far in my science classes, the  │ │
   │                        │ │           │ scientific consensus seems to be that climate change is a real         │ │
   │                        │ │           │ phenomenon and human activities are contributing to it. I find the     │ │
   │                        │ │           │ topic really interesting and important to understand. I try to stay up │ │
   │                        │ │           │ to date by reading articles and reports from reputable scientific      │ │
   │                        │ │           │ sources. At the same time, I know there's still a lot of debate around │ │
   │                        │ │           │ the specific impacts and best solutions. I'm eager to continue         │ │
   │                        │ │           │ learning more as I progress in my studies."                            │ │
   │                        │ │ read      │ 'Yes'                                                                  │ │
   │                        │ └───────────┴────────────────────────────────────────────────────────────────────────┘ │
   │ prompt                 │ ┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
   │                        │ ┃ Attribute               ┃ Value                                                    ┃ │
   │                        │ ┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩ │
   │                        │ │ important_user_prompt   │ Prompt(text="""On a scale from 1 to 5, how important to  │ │
   │                        │ │                         │ you is climate change?                                   │ │
   │                        │ │                         │                                                          │ │
   │                        │ │                         │ 0 : Not at all                                           │ │
   │                        │ │                         │                                                          │ │
   │                        │ │                         │ 1 :                                                      │ │
   │                        │ │                         │                                                          │ │
   │                        │ │                         │ 2 :                                                      │ │
   │                        │ │                         │                                                          │ │
   │                        │ │                         │ 3 :                                                      │ │
   │                        │ │                         │                                                          │ │
   │                        │ │                         │ 4 :                                                      │ │
   │                        │ │                         │                                                          │ │
   │                        │ │                         │ 5 : Very much                                            │ │
   │                        │ │                         │                                                          │ │
   │                        │ │                         │ Only 1 option may be selected.                           │ │
   │                        │ │                         │                                                          │ │
   │                        │ │                         │ Respond only with the code corresponding to one of the   │ │
   │                        │ │                         │ options. E.g., "1" or "5" by itself.                     │ │
   │                        │ │                         │                                                          │ │
   │                        │ │                         │ After the answer, you can put a comment explaining why   │ │
   │                        │ │                         │ you chose that option on the next line.""")              │ │
   │                        │ │ important_system_prompt │ Prompt(text="""You are answering questions as if you     │ │
   │                        │ │                         │ were a human. Do not break character. You are an agent   │ │
   │                        │ │                         │ with the following persona:                              │ │
   │                        │ │                         │ {'persona': 'student'}""")                               │ │
   │                        │ │ opinions_user_prompt    │ Prompt(text="""What are your opinions on climate         │ │
   │                        │ │                         │ change?""")                                              │ │
   │                        │ │ opinions_system_prompt  │ Prompt(text="""You are answering questions as if you     │ │
   │                        │ │                         │ were a human. Do not break character. You are an agent   │ │
   │                        │ │                         │ with the following persona:                              │ │
   │                        │ │                         │ {'persona': 'student'}""")                               │ │
   │                        │ │ read_user_prompt        │ Prompt(text="""                                          │ │
   │                        │ │                         │ Have you read any books about climate change?            │ │
   │                        │ │                         │                                                          │ │
   │                        │ │                         │                                                          │ │
   │                        │ │                         │ Yes                                                      │ │
   │                        │ │                         │                                                          │ │
   │                        │ │                         │ No                                                       │ │
   │                        │ │                         │                                                          │ │
   │                        │ │                         │ I do not know                                            │ │
   │                        │ │                         │                                                          │ │
   │                        │ │                         │                                                          │ │
   │                        │ │                         │ Only 1 option may be selected.                           │ │
   │                        │ │                         │                                                          │ │
   │                        │ │                         │ Respond only with a string corresponding to one of the   │ │
   │                        │ │                         │ options.                                                 │ │
   │                        │ │                         │                                                          │ │
   │                        │ │                         │                                                          │ │
   │                        │ │                         │ After the answer, you can put a comment explaining why   │ │
   │                        │ │                         │ you chose that option on the next line.""")              │ │
   │                        │ │ read_system_prompt      │ Prompt(text="""You are answering questions as if you     │ │
   │                        │ │                         │ were a human. Do not break character. You are an agent   │ │
   │                        │ │                         │ with the following persona:                              │ │
   │                        │ │                         │ {'persona': 'student'}""")                               │ │
   │                        │ └─────────────────────────┴──────────────────────────────────────────────────────────┘ │
   │ raw_model_response     │ ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
   │                        │ ┃ Attribute                    ┃ Value                                               ┃ │
   │                        │ ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩ │
   │                        │ │ important_raw_model_response │ {'id': 'msg_01HGaPNDtj6fkCLdbdy3h4HA', 'content':   │ │
   │                        │ │                              │ [{'text': "4\n\nAs a student, I'm quite concerned   │ │
   │                        │ │                              │ about climate change and its long-term impacts on   │ │
   │                        │ │                              │ our planet and future generations. It's a major     │ │
   │                        │ │                              │ issue we learn about in school, and I feel it's     │ │
   │                        │ │                              │ important to be informed and take action where we   │ │
   │                        │ │                              │ can.", 'type': 'text'}], 'model':                   │ │
   │                        │ │                              │ 'claude-3-5-sonnet-20240620', 'role': 'assistant',  │ │
   │                        │ │                              │ 'stop_reason': 'end_turn', 'stop_sequence': None,   │ │
   │                        │ │                              │ 'type': 'message', 'usage': {'input_tokens': 152,   │ │
   │                        │ │                              │ 'output_tokens': 57}}                               │ │
   │                        │ │ important_cost               │ 0.001310994813023199                                │ │
   │                        │ │ important_one_usd_buys       │ 762.779524423873                                    │ │
   │                        │ │ opinions_raw_model_response  │ {'id': 'msg_017mQNAmbkvzuLLtpe7HzhiS', 'content':   │ │
   │                        │ │                              │ [{'text': "As a student, I'm still learning about   │ │
   │                        │ │                              │ climate change and forming my views on it. From     │ │
   │                        │ │                              │ what I've studied so far in my science classes, the │ │
   │                        │ │                              │ scientific consensus seems to be that climate       │ │
   │                        │ │                              │ change is a real phenomenon and human activities    │ │
   │                        │ │                              │ are contributing to it. I find the topic really     │ │
   │                        │ │                              │ interesting and important to understand. I try to   │ │
   │                        │ │                              │ stay up to date by reading articles and reports     │ │
   │                        │ │                              │ from reputable scientific sources. At the same      │ │
   │                        │ │                              │ time, I know there's still a lot of debate around   │ │
   │                        │ │                              │ the specific impacts and best solutions. I'm eager  │ │
   │                        │ │                              │ to continue learning more as I progress in my       │ │
   │                        │ │                              │ studies.", 'type': 'text'}], 'model':               │ │
   │                        │ │                              │ 'claude-3-5-sonnet-20240620', 'role': 'assistant',  │ │
   │                        │ │                              │ 'stop_reason': 'end_turn', 'stop_sequence': None,   │ │
   │                        │ │                              │ 'type': 'message', 'usage': {'input_tokens': 49,    │ │
   │                        │ │                              │ 'output_tokens': 119}}                              │ │
   │                        │ │ opinions_cost                │ 0.0019319907810452126                               │ │
   │                        │ │ opinions_one_usd_buys        │ 517.6008135292432                                   │ │
   │                        │ │ read_raw_model_response      │ {'id': 'msg_01VwAiiNMiwTZQ6Q4jU5hPof', 'content':   │ │
   │                        │ │                              │ [{'text': "Yes\n\nAs a student, I've likely had to  │ │
   │                        │ │                              │ read at least one book about climate change for a   │ │
   │                        │ │                              │ science or environmental studies class. It's a      │ │
   │                        │ │                              │ major topic covered in many curricula these days.", │ │
   │                        │ │                              │ 'type': 'text'}], 'model':                          │ │
   │                        │ │                              │ 'claude-3-5-sonnet-20240620', 'role': 'assistant',  │ │
   │                        │ │                              │ 'stop_reason': 'end_turn', 'stop_sequence': None,   │ │
   │                        │ │                              │ 'type': 'message', 'usage': {'input_tokens': 114,   │ │
   │                        │ │                              │ 'output_tokens': 43}}                               │ │
   │                        │ │ read_cost                    │ 0.000986996091017493                                │ │
   │                        │ │ read_one_usd_buys            │ 1013.1752385859008                                  │ │
   │                        │ └──────────────────────────────┴─────────────────────────────────────────────────────┘ │
   │ survey                 │ ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
   │                        │ ┃ Questions                                                                          ┃ │
   │                        │ ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩ │
   │                        │ │ ┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓ │ │
   │                        │ │ ┃ Question Name ┃ Question Type ┃ Question Text               ┃ Options          ┃ │ │
   │                        │ │ ┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩ │ │
   │                        │ │ │ important     │ linear_scale  │ On a scale from 1 to 5, how │ 0, 1, 2, 3, 4, 5 │ │ │
   │                        │ │ │               │               │ important to you is {{      │                  │ │ │
   │                        │ │ │               │               │ topic }}?                   │                  │ │ │
   │                        │ │ └───────────────┴───────────────┴─────────────────────────────┴──────────────────┘ │ │
   │                        │ │ ┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓ │ │
   │                        │ │ ┃ Question Name ┃ Question Type ┃ Question Text                        ┃ Options ┃ │ │
   │                        │ │ ┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩ │ │
   │                        │ │ │ opinions      │ free_text     │ What are your opinions on {{ topic   │ None    │ │ │
   │                        │ │ │               │               │ }}?                                  │         │ │ │
   │                        │ │ └───────────────┴───────────────┴──────────────────────────────────────┴─────────┘ │ │
   │                        │ │ ┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┓ │ │
   │                        │ │ ┃ Question Name ┃ Question Type   ┃ Question Text        ┃ Options               ┃ │ │
   │                        │ │ ┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━┩ │ │
   │                        │ │ │ read          │ multiple_choice │ Have you read any    │ Yes, No, I do not     │ │ │
   │                        │ │ │               │                 │ books about {{ topic │ know                  │ │ │
   │                        │ │ │               │                 │ }}?                  │                       │ │ │
   │                        │ │ └───────────────┴─────────────────┴──────────────────────┴───────────────────────┘ │ │
   │                        │ └────────────────────────────────────────────────────────────────────────────────────┘ │
   │ question_to_attributes │ ┏━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
   │                        │ ┃ Attribute ┃ Value                                                                  ┃ │
   │                        │ ┡━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩ │
   │                        │ │ important │ {'question_text': 'On a scale from 1 to 5, how important to you is {{  │ │
   │                        │ │           │ topic }}?', 'question_type': 'linear_scale', 'question_options': [0,   │ │
   │                        │ │           │ 1, 2, 3, 4, 5]}                                                        │ │
   │                        │ │ opinions  │ {'question_text': 'What are your opinions on {{ topic }}?',            │ │
   │                        │ │           │ 'question_type': 'free_text', 'question_options': None}                │ │
   │                        │ │ read      │ {'question_text': 'Have you read any books about {{ topic }}?',        │ │
   │                        │ │           │ 'question_type': 'multiple_choice', 'question_options': ['Yes', 'No',  │ │
   │                        │ │           │ 'I do not know']}                                                      │ │
   │                        │ └───────────┴────────────────────────────────────────────────────────────────────────┘ │
   │ generated_tokens       │ ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
   │                        │ ┃ Attribute                  ┃ Value                                                 ┃ │
   │                        │ ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩ │
   │                        │ │ important_generated_tokens │ "4\n\nAs a student, I'm quite concerned about climate │ │
   │                        │ │                            │ change and its long-term impacts on our planet and    │ │
   │                        │ │                            │ future generations. It's a major issue we learn about │ │
   │                        │ │                            │ in school, and I feel it's important to be informed   │ │
   │                        │ │                            │ and take action where we can."                        │ │
   │                        │ │ opinions_generated_tokens  │ "As a student, I'm still learning about climate       │ │
   │                        │ │                            │ change and forming my views on it. From what I've     │ │
   │                        │ │                            │ studied so far in my science classes, the scientific  │ │
   │                        │ │                            │ consensus seems to be that climate change is a real   │ │
   │                        │ │                            │ phenomenon and human activities are contributing to   │ │
   │                        │ │                            │ it. I find the topic really interesting and important │ │
   │                        │ │                            │ to understand. I try to stay up to date by reading    │ │
   │                        │ │                            │ articles and reports from reputable scientific        │ │
   │                        │ │                            │ sources. At the same time, I know there's still a lot │ │
   │                        │ │                            │ of debate around the specific impacts and best        │ │
   │                        │ │                            │ solutions. I'm eager to continue learning more as I   │ │
   │                        │ │                            │ progress in my studies."                              │ │
   │                        │ │ read_generated_tokens      │ "Yes\n\nAs a student, I've likely had to read at      │ │
   │                        │ │                            │ least one book about climate change for a science or  │ │
   │                        │ │                            │ environmental studies class. It's a major topic       │ │
   │                        │ │                            │ covered in many curricula these days."                │ │
   │                        │ └────────────────────────────┴───────────────────────────────────────────────────────┘ │
   │ comments_dict          │ ┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
   │                        │ ┃ Attribute         ┃ Value                                                          ┃ │
   │                        │ ┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩ │
   │                        │ │ important_comment │ "As a student, I'm quite concerned about climate change and    │ │
   │                        │ │                   │ its long-term impacts on our planet and future generations.    │ │
   │                        │ │                   │ It's a major issue we learn about in school, and I feel it's   │ │
   │                        │ │                   │ important to be informed and take action where we can."        │ │
   │                        │ │ opinions_comment  │ ''                                                             │ │
   │                        │ │ read_comment      │ "As a student, I've likely had to read at least one book about │ │
   │                        │ │                   │ climate change for a science or environmental studies class.   │ │
   │                        │ │                   │ It's a major topic covered in many curricula these days."      │ │
   │                        │ └───────────────────┴────────────────────────────────────────────────────────────────┘ │
   │ _combined_dict         │ None                                                                                   │
   │ _problem_keys          │ None                                                                                   │
   │ interview_hash         │ 1646262796627658719                                                                    │
   └────────────────────────┴────────────────────────────────────────────────────────────────────────────────────────┘


Results fields
^^^^^^^^^^^^^^

Results contain fields that can be accessed and analyzed individually or collectively.
We can see a list of these fields by calling the `columns` method:

.. code-block:: python

   results.columns


The following list will be returned for the results generated by the above code:

.. code-block:: text

   ['agent.agent_instruction',
   'agent.agent_name',
   'agent.persona',
   'answer.important',
   'answer.opinions',
   'answer.read',
   'comment.important_comment',
   'comment.opinions_comment',
   'comment.read_comment',
   'generated_tokens.important_generated_tokens',
   'generated_tokens.opinions_generated_tokens',
   'generated_tokens.read_generated_tokens',
   'iteration.iteration',
   'model.frequency_penalty',
   'model.logprobs',
   'model.max_tokens',
   'model.model',
   'model.presence_penalty',
   'model.temperature',
   'model.top_logprobs',
   'model.top_p',
   'prompt.important_system_prompt',
   'prompt.important_user_prompt',
   'prompt.opinions_system_prompt',
   'prompt.opinions_user_prompt',
   'prompt.read_system_prompt',
   'prompt.read_user_prompt',
   'question_options.important_question_options',
   'question_options.opinions_question_options',
   'question_options.read_question_options',
   'question_text.important_question_text',
   'question_text.opinions_question_text',
   'question_text.read_question_text',
   'question_type.important_question_type',
   'question_type.opinions_question_type',
   'question_type.read_question_type',
   'raw_model_response.important_cost',
   'raw_model_response.important_one_usd_buys',
   'raw_model_response.important_raw_model_response',
   'raw_model_response.opinions_cost',
   'raw_model_response.opinions_one_usd_buys',
   'raw_model_response.opinions_raw_model_response',
   'raw_model_response.read_cost',
   'raw_model_response.read_one_usd_buys',
   'raw_model_response.read_raw_model_response',
   'scenario.topic']
   

The columns include information about each *agent*, *model* and corresponding *prompts* used to simulate the *answer* to each *question* and *scenario* in the survey, together with each *raw model response*.
If the survey was run multiple times (`run(n=<integer>)`) then the `iteration.iteration` column will show the iteration number for each result.

*Agent* information:

* **agent.instruction**: The instruction for the agent. This field is the optional instruction that was passed to the agent when it was created.
* **agent.agent_name**: This field is always included in any `Results` object. It contains a unique identifier for each `Agent` that can be specified when an agent is is created (`Agent(name=<name>, traits={<traits_dict>})`). If not specified, it is added automatically when results are generated (in the form `Agent_0`, etc.).
* **agent.persona**: Each of the `traits` that we pass to an agent is represented in a column of the results. Our example code created a "persona" trait for each agent, so our results include a "persona" column for this information. Note that the keys for the traits dictionary should be a valid Python keys.

*Answer* information:

* **answer.important**: Agent responses to the linear scale `important` question.
* **answer.opinions**: Agent responses to the free text `opinions` question.
* **answer.read**: Agent responses to the multiple choice `read` question.

A "comment" field is automatically included for every question in a survey other than free text questions, 
to allow the agent to optionally provide additional information about its response to the question
(unless the parameter `include_comment=False` is passed to a question when constructed):
* **comment.important_comment**: Agent commentary on responses to the `important` question.
* **comment.opinions_comment**: Agent commentary on responses to the `opinion` question. *Note that this field is empty because the question type is `free_text`.*
* **comment.read_comment**: Agent commentary on responses to the `read` question.

*Generated tokens* information:

* **generated_tokens.important_generated_tokens**: The generated tokens for the `important` question.
* **generated_tokens.opinions_generated_tokens**: The generated tokens for the `opinions` question.
* **generated_tokens.read_generated_tokens**: The generated tokens for the `read` question.

*Iteration* information:

The `iteration` column shows the number of the run (`run(n=<integer>)`) for the combination of components used (scenarios, agents and models).

*Model* information:

Each of `model` columns is a modifiable parameter of the models used to generate the responses.

* **model.frequency_penalty**: The frequency penalty for the model.
* **model.logprobs**: The logprobs for the model.
* **model.max_tokens**: The maximum number of tokens for the model.
* **model.model**: The name of the model used.
* **model.presence_penalty**: The presence penalty for the model.
* **model.temperature**: The temperature for the model.
* **model.top_logprobs**: The top logprobs for the model.
* **model.top_p**: The top p for the model.
* **model.use_cache**: Whether the model uses cache.

*Prompt* information:

* **prompt.important_system_prompt**: The system prompt for the `important` question.
* **prompt.important_user_prompt**: The user prompt for the `important` question.
* **prompt.opinions_system_prompt**: The system prompt for the `opinions` question.
* **prompt.opinions_user_prompt**: The user prompt for the `opinions` question.
* **prompt.read_system_prompt**: The system prompt for the `read` question.
* **prompt.read_user_prompt**: The user prompt for the `read` question.
For more details about prompts, please see the :ref:`prompts` section.

*Question* information:

* **question_options.important_question_options**: The options for the `important` question, if any.
* **question_options.opinions_question_options**: The options for the `opinions` question, if any.
* **question_options.read_question_options**: The options for the `read` question, if any.
* **question_text.important_question_text**: The text of the `important` question.
* **question_text.opinions_question_text**: The text of the `opinions` question.
* **question_text.read_question_text**: The text of the `read` question.
* **question_type.important_question_type**: The type of the `important` question.
* **question_type.opinions_question_type**: The type of the `opinions` question.
* **question_type.read_question_type**: The type of the `read` question.

*Raw model response* information:

* **raw_model_response.important_cost**: The cost of the result for the `important` question, applying the token quanities & prices.
* **raw_model_response.important_one_usd_buys**: The number of identical results for the `important` question that 1USD would cover. 
* **raw_model_response.important_raw_model_response**: The raw model response for the `important` question.
* **raw_model_response.opinions_cost**: The cost of the result for the `opinions` question, applying the token quanities & prices.
* **raw_model_response.opinions_one_usd_buys**: The number of identical results for the `opinions` question that 1USD would cover.
* **raw_model_response.opinions_raw_model_response**: The raw model response for the `opinions` question.
* **raw_model_response.read_cost**: The cost of the result for the `read` question, applying the token quanities & prices.
* **raw_model_response.read_one_usd_buys**: The number of identical results for the `read` question that 1USD would cover.
* **raw_model_response.read_raw_model_response**: The raw model response for the `read` question.

Note that the cost of a result for a question is specific to the components (scenario, agent, model used with it). 

*Scenario* information:

* **scenario.topic**: The values provided for the "topic" scenario for the questions.


Creating tables by selecting/dropping and printing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Each of these columns can be accessed directly by calling the `select()` method and passing the column names.
Alternatively, we can specify the columns to exclude by calling the `drop()` method.
These methods can be chained together with the `print()` method to display the specified columns in a table format.

For example, the following code will print a table showing the answers for `read` and `important` together with `model`, `persona` and `topic` columns
(because the column names are unique we can drop the `model`, `agent`, `scenario` and `answer` prefixes when selecting them):

.. code-block:: python

   results = survey.by(scenarios).by(agents).by(models).run() # Running the survey once
   results.select("model", "persona", "topic", "read", "important").print(format="rich")


A table with the selected columns will be printed:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━┓
   ┃ model                      ┃ agent     ┃ scenario       ┃ answer ┃ answer     ┃
   ┃ .model                     ┃ .persona  ┃ .topic         ┃ .read  ┃ .important ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━┩
   │ claude-3-5-sonnet-20240620 │ student   │ climate change │ Yes    │ 4          │
   ├────────────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4o                     │ student   │ climate change │ Yes    │ 5          │
   ├────────────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ claude-3-5-sonnet-20240620 │ student   │ data privacy   │ No     │ 3          │
   ├────────────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4o                     │ student   │ data privacy   │ Yes    │ 5          │
   ├────────────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ claude-3-5-sonnet-20240620 │ celebrity │ climate change │ Yes    │ 4          │
   ├────────────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4o                     │ celebrity │ climate change │ Yes    │ 5          │
   ├────────────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ claude-3-5-sonnet-20240620 │ celebrity │ data privacy   │ No     │ 4          │
   ├────────────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4o                     │ celebrity │ data privacy   │ Yes    │ 5          │
   └────────────────────────────┴───────────┴────────────────┴────────┴────────────┘


Sorting results
^^^^^^^^^^^^^^^

We can sort the columns by calling the `sort_by` method and passing it the column name to sort by:

.. code-block:: python

   (
      results
      .sort_by("model", reverse=False)
      .select("model", "persona", "topic", "read", "important")
      .print(format="rich")
   )


The following table will be printed:

.. code-block:: text
   
   ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━┓
   ┃ model                      ┃ agent     ┃ scenario       ┃ answer ┃ answer     ┃
   ┃ .model                     ┃ .persona  ┃ .topic         ┃ .read  ┃ .important ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━┩
   │ claude-3-5-sonnet-20240620 │ student   │ climate change │ Yes    │ 4          │
   ├────────────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ claude-3-5-sonnet-20240620 │ student   │ data privacy   │ No     │ 3          │
   ├────────────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ claude-3-5-sonnet-20240620 │ celebrity │ climate change │ Yes    │ 4          │
   ├────────────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ claude-3-5-sonnet-20240620 │ celebrity │ data privacy   │ No     │ 4          │
   ├────────────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4o                     │ student   │ climate change │ Yes    │ 5          │
   ├────────────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4o                     │ student   │ data privacy   │ Yes    │ 5          │
   ├────────────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4o                     │ celebrity │ climate change │ Yes    │ 5          │
   ├────────────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4o                     │ celebrity │ data privacy   │ Yes    │ 5          │
   └────────────────────────────┴───────────┴────────────────┴────────┴────────────┘


The `sort_by` method can be applied multiple times:

.. code-block:: python

   (
      results
      .sort_by("model", reverse=False)
      .sort_by("persona", reverse=True)
      .select("model", "persona", "topic", "read", "important")
      .print(format="rich")
   )


The following table will be printed:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━┓
   ┃ model                      ┃ agent     ┃ scenario       ┃ answer ┃ answer     ┃
   ┃ .model                     ┃ .persona  ┃ .topic         ┃ .read  ┃ .important ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━┩
   │ claude-3-5-sonnet-20240620 │ student   │ climate change │ Yes    │ 4          │
   ├────────────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ claude-3-5-sonnet-20240620 │ student   │ data privacy   │ No     │ 3          │
   ├────────────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4o                     │ student   │ climate change │ Yes    │ 5          │
   ├────────────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4o                     │ student   │ data privacy   │ Yes    │ 5          │
   ├────────────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ claude-3-5-sonnet-20240620 │ celebrity │ climate change │ Yes    │ 4          │
   ├────────────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ claude-3-5-sonnet-20240620 │ celebrity │ data privacy   │ No     │ 4          │
   ├────────────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4o                     │ celebrity │ climate change │ Yes    │ 5          │
   ├────────────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4o                     │ celebrity │ data privacy   │ Yes    │ 5          │
   └────────────────────────────┴───────────┴────────────────┴────────┴────────────┘


Labeling results
^^^^^^^^^^^^^^^^

We can also add some table labels by passing a dictionary to the `pretty_labels` argument of the `print` method
(note that we need to include the column prefixes when specifying the table labels, as shown below):

.. code-block:: python

   (
      results
      .sort_by("model", reverse=False)
      .sort_by("persona", reverse=True)
      .select("model", "persona", "topic", "read", "important")
      .print(pretty_labels={
         "model.model": "LLM", 
         "agent.persona": "Agent", 
         "scenario.topic": "Topic", 
         "answer.read": q3.question_text,
         "answer.important": q1.question_text
         }, format="rich")
   )


The following table will be printed:

.. code-block:: text
      
   ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃                           ┃           ┃                ┃                            ┃ On a scale from 1 to 5,   ┃
   ┃                           ┃           ┃                ┃ Have you read any books    ┃ how important to you is   ┃
   ┃ LLM                       ┃ Agent     ┃ Topic          ┃ about {{ topic }}?         ┃ {{ topic }}?              ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
   │ claude-3-5-sonnet-202406… │ student   │ climate change │ Yes                        │ 4                         │
   ├───────────────────────────┼───────────┼────────────────┼────────────────────────────┼───────────────────────────┤
   │ claude-3-5-sonnet-202406… │ student   │ data privacy   │ No                         │ 3                         │
   ├───────────────────────────┼───────────┼────────────────┼────────────────────────────┼───────────────────────────┤
   │ gpt-4o                    │ student   │ climate change │ Yes                        │ 5                         │
   ├───────────────────────────┼───────────┼────────────────┼────────────────────────────┼───────────────────────────┤
   │ gpt-4o                    │ student   │ data privacy   │ Yes                        │ 5                         │
   ├───────────────────────────┼───────────┼────────────────┼────────────────────────────┼───────────────────────────┤
   │ claude-3-5-sonnet-202406… │ celebrity │ climate change │ Yes                        │ 4                         │
   ├───────────────────────────┼───────────┼────────────────┼────────────────────────────┼───────────────────────────┤
   │ claude-3-5-sonnet-202406… │ celebrity │ data privacy   │ No                         │ 4                         │
   ├───────────────────────────┼───────────┼────────────────┼────────────────────────────┼───────────────────────────┤
   │ gpt-4o                    │ celebrity │ climate change │ Yes                        │ 5                         │
   ├───────────────────────────┼───────────┼────────────────┼────────────────────────────┼───────────────────────────┤
   │ gpt-4o                    │ celebrity │ data privacy   │ Yes                        │ 5                         │
   └───────────────────────────┴───────────┴────────────────┴────────────────────────────┴───────────────────────────┘


Filtering results
^^^^^^^^^^^^^^^^^

Results can be filtered by using the `filter` method and passing it a logical expression identifying the results that should be selected.
For example, the following code will filter results where the answer to `important` is "5" and then just print the `topic` and `important_comment` columns:

.. code-block:: python

   (
      results
      .filter("important == 5")
      .select("topic", "important_comment")
      .print(format="rich")
   )


This will return an abbreviated table:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ scenario       ┃ comment                                                                                        ┃
   ┃ .topic         ┃ .important_comment                                                                             ┃
   ┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
   │ climate change │ Climate change is a critical issue that affects everyone and everything on the planet. As a    │
   │                │ student, I believe it's essential to address it for our future.                                │
   ├────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────┤
   │ data privacy   │ Data privacy is crucial to me because it protects my personal information and ensures that my  │
   │                │ data is not misused or accessed without my consent.                                            │
   ├────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────┤
   │ climate change │ Climate change is one of the most pressing issues of our time, and as a public figure, I       │
   │                │ believe it's crucial to use my platform to raise awareness and advocate for sustainable        │
   │                │ practices.                                                                                     │
   ├────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────┤
   │ data privacy   │ Data privacy is crucial, especially as a public figure. Protecting personal information is     │
   │                │ essential to maintaining security and trust.                                                   │
   └────────────────┴────────────────────────────────────────────────────────────────────────────────────────────────┘


**Note:** The `filter` method allows us to pass the unique short names of the columns (without the prefixes) when specifying the logical expression.
However, because the `model.model` column name is also a prefix, we need to include the prefix when filtering by this column, as shown in the example below:

.. code-block:: python

   (
      results
      .filter("model.model == 'gpt-4o'")
      .select("model", "persona", "topic", "read", "important")
      .print(format="rich")
   )


This will return a table of results where the model is "gpt-4o":

.. code-block:: text

   ┏━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━┓
   ┃ model  ┃ agent     ┃ scenario       ┃ answer ┃ answer     ┃
   ┃ .model ┃ .persona  ┃ .topic         ┃ .read  ┃ .important ┃
   ┡━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━┩
   │ gpt-4o │ student   │ climate change │ Yes    │ 5          │
   ├────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4o │ student   │ data privacy   │ Yes    │ 5          │
   ├────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4o │ celebrity │ climate change │ Yes    │ 5          │
   ├────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4o │ celebrity │ data privacy   │ Yes    │ 5          │
   └────────┴───────────┴────────────────┴────────┴────────────┘


Limiting results
^^^^^^^^^^^^^^^^

We can select and print a limited number of results by passing the desired number of `max_rows` to the `print()` method.
This can be useful for quickly checking the first few results:

.. code-block:: python

   (
      results
      .select("model", "persona", "topic", "read", "important")
      .print(max_rows=4, format="rich")
   )


This will return a table of the selected components of the first 4 results:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━┓
   ┃ model                      ┃ agent    ┃ scenario       ┃ answer ┃ answer     ┃
   ┃ .model                     ┃ .persona ┃ .topic         ┃ .read  ┃ .important ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━┩
   │ claude-3-5-sonnet-20240620 │ student  │ climate change │ Yes    │ 4          │
   ├────────────────────────────┼──────────┼────────────────┼────────┼────────────┤
   │ gpt-4o                     │ student  │ climate change │ Yes    │ 5          │
   ├────────────────────────────┼──────────┼────────────────┼────────┼────────────┤
   │ claude-3-5-sonnet-20240620 │ student  │ data privacy   │ No     │ 3          │
   ├────────────────────────────┼──────────┼────────────────┼────────┼────────────┤
   │ gpt-4o                     │ student  │ data privacy   │ Yes    │ 5          │
   └────────────────────────────┴──────────┴────────────────┴────────┴────────────┘


Sampling results
^^^^^^^^^^^^^^^^

We can select a sample of `n` results by passing the desired number of random results to the `sample()` method.
This can be useful for checking a random subset of the results with different parameters:

.. code-block:: python

   sample_results = results.sample(2)

   (
      sample_results
      .sort_by("model", reverse=False)
      .select("model", "persona", "topic", "read", "important")
      .print(format="rich")
   )


This will return a table of the specified number of randomly selected results:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━┓
   ┃ model                      ┃ agent    ┃ scenario       ┃ answer ┃ answer     ┃
   ┃ .model                     ┃ .persona ┃ .topic         ┃ .read  ┃ .important ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━┩
   │ claude-3-5-sonnet-20240620 │ student  │ data privacy   │ No     │ 3          │
   ├────────────────────────────┼──────────┼────────────────┼────────┼────────────┤
   │ claude-3-5-sonnet-20240620 │ student  │ climate change │ Yes    │ 4          │
   └────────────────────────────┴──────────┴────────────────┴────────┴────────────┘


Shuffling results
^^^^^^^^^^^^^^^^^

We can shuffle results by calling the `shuffle()` method.
This can be useful for quickly checking the first few results:

.. code-block:: python

   shuffle_results = results.shuffle()

   (
      shuffle_results
      .select("model", "persona", "topic", "read", "important")
      .print(format="rich")
   )


This will return a table of shuffled results:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━┓
   ┃ model                      ┃ agent     ┃ scenario       ┃ answer ┃ answer     ┃
   ┃ .model                     ┃ .persona  ┃ .topic         ┃ .read  ┃ .important ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━┩
   │ claude-3-5-sonnet-20240620 │ celebrity │ climate change │ Yes    │ 4          │
   ├────────────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ claude-3-5-sonnet-20240620 │ student   │ climate change │ Yes    │ 4          │
   ├────────────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ claude-3-5-sonnet-20240620 │ student   │ data privacy   │ No     │ 3          │
   ├────────────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4o                     │ celebrity │ data privacy   │ Yes    │ 5          │
   ├────────────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4o                     │ student   │ data privacy   │ Yes    │ 5          │
   ├────────────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4o                     │ student   │ climate change │ Yes    │ 5          │
   ├────────────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4o                     │ celebrity │ climate change │ Yes    │ 5          │
   ├────────────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ claude-3-5-sonnet-20240620 │ celebrity │ data privacy   │ No     │ 4          │
   └────────────────────────────┴───────────┴────────────────┴────────┴────────────┘


Adding results
^^^^^^^^^^^^^^

We can add results together straightforwardly by using the `+` operator:

.. code-block:: python

   add_results = results + results


We can see that the results have doubled:

.. code-block:: text

   len(add_results)


This will return the number of results:

.. code-block:: text

   16


Displaying results in a tree format
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We can display the results in a tree format using the `tree` method, which displays the results in a nested format for each of the components: `model`, `scenario`, `agent`, `answer`, `question`, `iteration`.
The method takes a list parameter `fold_attributes` for the attributes to be folded, and an option list parmeter `drop` for fields to be excluded from the display.

For example, the following code will display the results in a tree format for the `model` and `scenario` components, excluding the `iteration` component:

.. code-block:: python

   results.tree(fold_attributes=["model", "scenario"], drop=["iteration"])


This will display the results in a tree format:

.. code-block:: text

   model: Model(model_name = 'claude-3-5-sonnet-20240620', temperature = 0.5, max_tokens = 1000, top_p = 1, frequency_penalty = 0, presence_penalty = 0, logprobs = False, top_logprobs = 3)
   
   model: Model(model_name = 'gpt-4o', temperature = 0.5, max_tokens = 1000, top_p = 1, frequency_penalty = 0, presence_penalty = 0, logprobs = False, top_logprobs = 3) 
   

Generating HTML reports
^^^^^^^^^^^^^^^^^^^^^^^

We can generate an HTML report of the results by calling the `generate_html` and `save_html` methods.
The `generate_html` method will create an HTML report of the results, and the `save_html` method will save the report to a specified file path (default filename: `output.html`).


.. code-block:: python

   results.generate_html().save_html("output.html")


   
Interacting via SQL
^^^^^^^^^^^^^^^^^^^

We can interact with the results via SQL using the `sql` method.
This is done by passing a SQL query and a `shape` ("long" or "wide") for the resulting table, where the table name in the query is "self".

The "wide" shape will return a table with each result as a row and columns for the selected columns of the results.
For example, the following code will return a table showing the `model`, `persona`, `read` and `important` columns for the first 4 results:

.. code-block:: python

   results.sql("select model, persona, read, important from self limit 4", shape="wide")


This following table will be displayed:

.. code-block:: text

      model	                     persona	read	important
   0	claude-3-5-sonnet-20240620	student	Yes	4
   1	gpt-4o	                  student	Yes	5
   2	claude-3-5-sonnet-20240620	student	No	   3
   3	gpt-4o	                  student	Yes	5


The "long" shape lets us instead treat the components of the results as rows.
There are 4 columns in the resulting table: 

* **data_type**: The component type within the results (i.e., the column prefixes referred to above).
* **key**: The name of the component (e.g., the prefix `question_text`).
* **value**: The actual component (e.g., the individual question texts).
* **id**: The number of the `Result` object within the `Results`. 
Because a `Result` includes answers for all of the questions in a survey, the all of the questions of a `Result` share the same `id`.

For example, the following code will return a table showing the `question_text` data for all of the results:

.. code-block:: python

   results.sql("select * from self where data_type = 'question_text'", shape="long")


This following table will be displayed:

.. code-block:: text

      id	data_type	   key	                  value
   0	0	question_text	important_question_text	On a scale from 1 to 5, how important to you i...
   1	0	question_text	opinions_question_text	What are your opinions on {{ topic }}?
   2	0	question_text	read_question_text	   Have you read any books about {{ topic }}?
   3	1	question_text	important_question_text	On a scale from 1 to 5, how important to you i...
   4	1	question_text	opinions_question_text	What are your opinions on {{ topic }}?
   5	1	question_text	read_question_text	   Have you read any books about {{ topic }}?
   6	2	question_text	important_question_text	On a scale from 1 to 5, how important to you i...
   7	2	question_text	opinions_question_text	What are your opinions on {{ topic }}?
   8	2	question_text	read_question_text	   Have you read any books about {{ topic }}?
   9	3	question_text	important_question_text	On a scale from 1 to 5, how important to you i...
   10	3	question_text	opinions_question_text	What are your opinions on {{ topic }}?
   11	3	question_text	read_question_text	   Have you read any books about {{ topic }}?
   12	4	question_text	important_question_text	On a scale from 1 to 5, how important to you i...
   13	4	question_text	opinions_question_text	What are your opinions on {{ topic }}?
   14	4	question_text	read_question_text	   Have you read any books about {{ topic }}?
   15	5	question_text	important_question_text	On a scale from 1 to 5, how important to you i...
   16	5	question_text	opinions_question_text	What are your opinions on {{ topic }}?
   17	5	question_text	read_question_text	   Have you read any books about {{ topic }}?
   18	6	question_text	important_question_text	On a scale from 1 to 5, how important to you i...
   19	6	question_text	opinions_question_text	What are your opinions on {{ topic }}?
   20	6	question_text	read_question_text	   Have you read any books about {{ topic }}?
   21	7	question_text	important_question_text	On a scale from 1 to 5, how important to you i...
   22	7	question_text	opinions_question_text	What are your opinions on {{ topic }}?
   23	7	question_text	read_question_text	   Have you read any books about {{ topic }}?


Dataframes
^^^^^^^^^^

We can also export results to other formats.
The `to_pandas` method will turn our results into a Pandas dataframe:

.. code-block:: python

   results.to_pandas()


For example, here we use it to create a dataframe consisting of the models, personas and the answers to the `important` question:

.. code-block:: python

   results.to_pandas()[["model.model", "agent.persona", "answer.important"]]


This will display our new dataframe:

.. code-block:: text

      model.model	               agent.persona	answer.important
   0	claude-3-5-sonnet-20240620	student	      4
   1	gpt-4o	                  student	      5
   2	claude-3-5-sonnet-20240620	student	      3
   3	gpt-4o	                  student	      5
   4	claude-3-5-sonnet-20240620	celebrity	   4
   5	gpt-4o	                  celebrity	   5
   6	claude-3-5-sonnet-20240620	celebrity	   4
   7	gpt-4o	                  celebrity	   5


Exporting to CSV or JSON
^^^^^^^^^^^^^^^^^^^^^^^^

The `to_csv` method will write the results to a CSV file:

.. code-block:: python

   results.to_pandas().to_csv("results.csv")


The `to_json` method will write the results to a JSON file:

.. code-block:: python

   results.to_pandas().to_json("results.json")



Exceptions
^^^^^^^^^^

If any exceptions are raised when the survey is run a detailed exceptions report is generated and will open automatically.
See the :ref:`exceptions` section for more information on exceptions.



Result class
------------

.. automodule:: edsl.results.Result
   :members: rich_print, 
   :inherited-members:
   :exclude-members: 
   :undoc-members:
   :special-members: __init__

Results class
-------------

.. automodule:: edsl.results.Results
   :members:
   :inherited-members:
   :exclude-members: append, clear, copy, count, extend, index, insert, pop, remove, reverse, sort, known_data_types, Mixins, main, PromptDict
   :undoc-members:
   :special-members: __init__

