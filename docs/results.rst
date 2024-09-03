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
   from edsl import QuestionLinearScale, QuestionFreeText, QuestionYesNo

   q1 = QuestionLinearScale(
      question_name = "important",
      question_text = "How much do you care about {{ topic }}?",
      question_options = [0, 1, 2, 3, 4, 5],
      option_labels = {0:"Not at all", 5:"A lot"}
   )

   q2 = QuestionFreeText(
      question_name = "feel",
      question_text = "How do you feel about {{ topic }}?"
   )

   q3 = QuestionYesNo(
      question_name = "read",
      question_text = "Have you read any books about {{ topic }}?"
   )

   # Optionally parameterize the questions with scenarios
   from edsl import ScenarioList, Scenario

   scenarios = ScenarioList(
      Scenario({"topic": t}) for t in ["climate change", "data privacy"]
   )

   # Optionally create agents with traits
   from edsl import AgentList, Agent

   agents = AgentList(
      Agent(traits = {"persona": p}) for p in ["student", "celebrity"]
   )

   # Optionally specify language models
   from edsl import ModelList, Model

   models = ModelList(
      Model(m) for m in ['claude-3-5-sonnet-20240620', 'gemini-pro', 'gpt-4o']
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
         "edsl_version": "0.1.30.dev3",
         "edsl_class_name": "Agent"
      },
      "scenario": {
         "topic": "climate change",
         "edsl_version": "0.1.30.dev3",
         "edsl_class_name": "Scenario"
      },
      "model": {
         "model": "gpt-4-0125-preview",
         "parameters": {
               "temperature": 0.5,
               "max_tokens": 1000,
               "top_p": 1,
               "frequency_penalty": 0,
               "presence_penalty": 0,
               "logprobs": false,
               "top_logprobs": 3
         },
         "edsl_version": "0.1.30.dev3",
         "edsl_class_name": "LanguageModel"
      },
      "iteration": 0,
      "answer": {
         "important": "5",
         "important_comment": "Climate change is a critical issue that affects all of us, and I'm deeply concerned about its impacts on our planet and future generations. It's important to take action and work towards sustainable solutions.",
         "feel": "I feel quite concerned about climate change. It's alarming to see the effects it's already having on our planet, from extreme weather events to the loss of biodiversity. It's something that affects all of us, and I believe it's crucial for both individuals and governments to take action to mitigate its impacts. The urgency to address this issue is clear, and I hope we can find sustainable solutions to protect our environment for future generations.",
         "read": "Yes",
         "read_comment": "I have read several books about climate change to better understand its impacts and the science behind it."
      },
      "prompt": {
         "feel_user_prompt": {
               "text": "You are being asked the following question: How do you feel about climate change?\nReturn a valid JSON formatted like this:\n{\"answer\": \"<put free text answer here>\"}",
               "class_name": "FreeText"
         },
         "feel_system_prompt": {
               "text": "You are answering questions as if you were a human. Do not break character. You are an agent with the following persona:\n{'persona': 'student'}",
               "class_name": "AgentInstruction"
         },
         "read_user_prompt": {
               "text": "You are being asked the following question: Have you read any books about climate change?\nThe options are\n\n0: Yes\n\n1: No\n\nReturn a valid JSON formatted like this, selecting only the number of the option:\n{\"answer\": <put answer code here>, \"comment\": \"<put explanation here>\"}\nOnly 1 option may be selected.",
               "class_name": "YesNo"
         },
         "read_system_prompt": {
               "text": "You are answering questions as if you were a human. Do not break character. You are an agent with the following persona:\n{'persona': 'student'}",
               "class_name": "AgentInstruction"
         },
         "important_user_prompt": {
               "text": "You are being asked the following question: How much do you care about climate change?\nThe options are\n\n0: 0\n\n1: 1\n\n2: 2\n\n3: 3\n\n4: 4\n\n5: 5\n\nReturn a valid JSON formatted like this, selecting only the code of the option (codes start at 0):\n{\"answer\": <put answer code here>, \"comment\": \"<put explanation here>\"}\nOnly 1 option may be selected.",
               "class_name": "LinearScale"
         },
         "important_system_prompt": {
               "text": "You are answering questions as if you were a human. Do not break character. You are an agent with the following persona:\n{'persona': 'student'}",
               "class_name": "AgentInstruction"
         }
      },
      "raw_model_response": {
         "important_raw_model_response": {
               "id": "chatcmpl-9pancU1Rt6VeeFNY4dCYiVj80A5Jh",
               "choices": [
                  {
                     "finish_reason": "stop",
                     "index": 0,
                     "logprobs": null,
                     "message": {
                           "content": "{\"answer\": 5, \"comment\": \"Climate change is a critical issue that affects all of us, and I'm deeply concerned about its impacts on our planet and future generations. It's important to take action and work towards sustainable solutions.\"}",
                           "role": "assistant",
                           "function_call": null,
                           "tool_calls": null
                     }
                  }
               ],
               "created": 1722083212,
               "model": "gpt-4-0125-preview",
               "object": "chat.completion",
               "service_tier": null,
               "system_fingerprint": null,
               "usage": {
                  "completion_tokens": 50,
                  "prompt_tokens": 141,
                  "total_tokens": 191
               }
         },
         "feel_raw_model_response": {
               "id": "chatcmpl-9pancuOj0pexzspNfMY1K1tqjSTuM",
               "choices": [
                  {
                     "finish_reason": "stop",
                     "index": 0,
                     "logprobs": null,
                     "message": {
                           "content": "```json\n{\"answer\": \"I feel quite concerned about climate change. It's alarming to see the effects it's already having on our planet, from extreme weather events to the loss of biodiversity. It's something that affects all of us, and I believe it's crucial for both individuals and governments to take action to mitigate its impacts. The urgency to address this issue is clear, and I hope we can find sustainable solutions to protect our environment for future generations.\"}\n```",
                           "role": "assistant",
                           "function_call": null,
                           "tool_calls": null
                     }
                  }
               ],
               "created": 1722083212,
               "model": "gpt-4-0125-preview",
               "object": "chat.completion",
               "service_tier": null,
               "system_fingerprint": null,
               "usage": {
                  "completion_tokens": 95,
                  "prompt_tokens": 77,
                  "total_tokens": 172
               }
         },
         "read_raw_model_response": {
               "id": "chatcmpl-9pance7VWhTUVXSEUXn1N6SA1IwgA",
               "choices": [
                  {
                     "finish_reason": "stop",
                     "index": 0,
                     "logprobs": null,
                     "message": {
                           "content": "{\"answer\": 0, \"comment\": \"I have read several books about climate change to better understand its impacts and the science behind it.\"}",
                           "role": "assistant",
                           "function_call": null,
                           "tool_calls": null
                     }
                  }
               ],
               "created": 1722083212,
               "model": "gpt-4-0125-preview",
               "object": "chat.completion",
               "service_tier": null,
               "system_fingerprint": null,
               "usage": {
                  "completion_tokens": 30,
                  "prompt_tokens": 113,
                  "total_tokens": 143
               }
         }
      },
      "question_to_attributes": {
         "important": {
               "question_text": "How much do you care about {{ topic }}?",
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
         "feel": {
               "question_text": "How do you feel about {{ topic }}?",
               "question_type": "free_text",
               "question_options": null
         },
         "read": {
               "question_text": "Have you read any books about {{ topic }}?",
               "question_type": "yes_no",
               "question_options": [
                  "Yes",
                  "No"
               ]
         }
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
   │                        │ │ current_question            │ Question('yes_no', question_name = """read""",       │ │
   │                        │ │                             │ question_text = """Have you read any books about {{  │ │
   │                        │ │                             │ topic }}?""", question_options = ['Yes', 'No'],      │ │
   │                        │ │                             │ model_instructions = {})                             │ │
   │                        │ └─────────────────────────────┴──────────────────────────────────────────────────────┘ │
   │ scenario               │             Scenario Attributes                                                        │
   │                        │ ┏━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓                                           │
   │                        │ ┃ Attribute  ┃ Value                       ┃                                           │
   │                        │ ┡━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩                                           │
   │                        │ │ data       │ {'topic': 'climate change'} │                                           │
   │                        │ │ name       │ None                        │                                           │
   │                        │ │ _has_image │ False                       │                                           │
   │                        │ └────────────┴─────────────────────────────┘                                           │
   │ model                  │                                     Language Model                                     │
   │                        │ ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
   │                        │ ┃ Attribute                   ┃ Value                                                ┃ │
   │                        │ ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩ │
   │                        │ │ model                       │ 'gpt-4-0125-preview'                                 │ │
   │                        │ │ parameters                  │ {'temperature': 0.5, 'max_tokens': 1000, 'top_p': 1, │ │
   │                        │ │                             │ 'frequency_penalty': 0, 'presence_penalty': 0,       │ │
   │                        │ │                             │ 'logprobs': False, 'top_logprobs': 3}                │ │
   │                        │ │ remote                      │ False                                                │ │
   │                        │ │ temperature                 │ 0.5                                                  │ │
   │                        │ │ max_tokens                  │ 1000                                                 │ │
   │                        │ │ top_p                       │ 1                                                    │ │
   │                        │ │ frequency_penalty           │ 0                                                    │ │
   │                        │ │ presence_penalty            │ 0                                                    │ │
   │                        │ │ logprobs                    │ False                                                │ │
   │                        │ │ top_logprobs                │ 3                                                    │ │
   │                        │ │ _LanguageModel__rate_limits │ {'rpm': 5000, 'tpm': 600000}                         │ │
   │                        │ └─────────────────────────────┴──────────────────────────────────────────────────────┘ │
   │ iteration              │ 0                                                                                      │
   │ answer                 │                                        Answers                                         │
   │                        │ ┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
   │                        │ ┃ Attribute         ┃ Value                                                          ┃ │
   │                        │ ┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩ │
   │                        │ │ important         │ '5'                                                            │ │
   │                        │ │ important_comment │ "Climate change is a critical issue that affects all of us,    │ │
   │                        │ │                   │ and I'm deeply concerned about its impacts on our planet and   │ │
   │                        │ │                   │ future generations. It's important to take action and work     │ │
   │                        │ │                   │ towards sustainable solutions."                                │ │
   │                        │ │ feel              │ "I feel quite concerned about climate change. It's alarming to │ │
   │                        │ │                   │ see the effects it's already having on our planet, from        │ │
   │                        │ │                   │ extreme weather events to the loss of biodiversity. It's       │ │
   │                        │ │                   │ something that affects all of us, and I believe it's crucial   │ │
   │                        │ │                   │ for both individuals and governments to take action to         │ │
   │                        │ │                   │ mitigate its impacts. The urgency to address this issue is     │ │
   │                        │ │                   │ clear, and I hope we can find sustainable solutions to protect │ │
   │                        │ │                   │ our environment for future generations."                       │ │
   │                        │ │ read              │ 'Yes'                                                          │ │
   │                        │ │ read_comment      │ 'I have read several books about climate change to better      │ │
   │                        │ │                   │ understand its impacts and the science behind it.'             │ │
   │                        │ └───────────────────┴────────────────────────────────────────────────────────────────┘ │
   │ prompt                 │ ┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
   │                        │ ┃ Attribute               ┃ Value                                                    ┃ │
   │                        │ ┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩ │
   │                        │ │ feel_user_prompt        │ Prompt(text="""You are being asked the following         │ │
   │                        │ │                         │ question: How do you feel about climate change?          │ │
   │                        │ │                         │ Return a valid JSON formatted like this:                 │ │
   │                        │ │                         │ {"answer": "<put free text answer here>"}""")            │ │
   │                        │ │ feel_system_prompt      │ Prompt(text="""You are answering questions as if you     │ │
   │                        │ │                         │ were a human. Do not break character. You are an agent   │ │
   │                        │ │                         │ with the following persona:                              │ │
   │                        │ │                         │ {'persona': 'student'}""")                               │ │
   │                        │ │ read_user_prompt        │ Prompt(text="""You are being asked the following         │ │
   │                        │ │                         │ question: Have you read any books about climate change?  │ │
   │                        │ │                         │ The options are                                          │ │
   │                        │ │                         │                                                          │ │
   │                        │ │                         │ 0: Yes                                                   │ │
   │                        │ │                         │                                                          │ │
   │                        │ │                         │ 1: No                                                    │ │
   │                        │ │                         │                                                          │ │
   │                        │ │                         │ Return a valid JSON formatted like this, selecting only  │ │
   │                        │ │                         │ the number of the option:                                │ │
   │                        │ │                         │ {"answer": <put answer code here>, "comment": "<put      │ │
   │                        │ │                         │ explanation here>"}                                      │ │
   │                        │ │                         │ Only 1 option may be selected.""")                       │ │
   │                        │ │ read_system_prompt      │ Prompt(text="""You are answering questions as if you     │ │
   │                        │ │                         │ were a human. Do not break character. You are an agent   │ │
   │                        │ │                         │ with the following persona:                              │ │
   │                        │ │                         │ {'persona': 'student'}""")                               │ │
   │                        │ │ important_user_prompt   │ Prompt(text="""You are being asked the following         │ │
   │                        │ │                         │ question: How much do you care about climate change?     │ │
   │                        │ │                         │ The options are                                          │ │
   │                        │ │                         │                                                          │ │
   │                        │ │                         │ 0: 0                                                     │ │
   │                        │ │                         │                                                          │ │
   │                        │ │                         │ 1: 1                                                     │ │
   │                        │ │                         │                                                          │ │
   │                        │ │                         │ 2: 2                                                     │ │
   │                        │ │                         │                                                          │ │
   │                        │ │                         │ 3: 3                                                     │ │
   │                        │ │                         │                                                          │ │
   │                        │ │                         │ 4: 4                                                     │ │
   │                        │ │                         │                                                          │ │
   │                        │ │                         │ 5: 5                                                     │ │
   │                        │ │                         │                                                          │ │
   │                        │ │                         │ Return a valid JSON formatted like this, selecting only  │ │
   │                        │ │                         │ the code of the option (codes start at 0):               │ │
   │                        │ │                         │ {"answer": <put answer code here>, "comment": "<put      │ │
   │                        │ │                         │ explanation here>"}                                      │ │
   │                        │ │                         │ Only 1 option may be selected.""")                       │ │
   │                        │ │ important_system_prompt │ Prompt(text="""You are answering questions as if you     │ │
   │                        │ │                         │ were a human. Do not break character. You are an agent   │ │
   │                        │ │                         │ with the following persona:                              │ │
   │                        │ │                         │ {'persona': 'student'}""")                               │ │
   │                        │ └─────────────────────────┴──────────────────────────────────────────────────────────┘ │
   │ raw_model_response     │ ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
   │                        │ ┃ Attribute                    ┃ Value                                               ┃ │
   │                        │ ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩ │
   │                        │ │ important_raw_model_response │ {'id': 'chatcmpl-9pancU1Rt6VeeFNY4dCYiVj80A5Jh',    │ │
   │                        │ │                              │ 'choices': [{'finish_reason': 'stop', 'index': 0,   │ │
   │                        │ │                              │ 'logprobs': None, 'message': {'content':            │ │
   │                        │ │                              │ '{"answer": 5, "comment": "Climate change is a      │ │
   │                        │ │                              │ critical issue that affects all of us, and I\'m     │ │
   │                        │ │                              │ deeply concerned about its impacts on our planet    │ │
   │                        │ │                              │ and future generations. It\'s important to take     │ │
   │                        │ │                              │ action and work towards sustainable solutions."}',  │ │
   │                        │ │                              │ 'role': 'assistant', 'function_call': None,         │ │
   │                        │ │                              │ 'tool_calls': None}}], 'created': 1722083212,       │ │
   │                        │ │                              │ 'model': 'gpt-4-0125-preview', 'object':            │ │
   │                        │ │                              │ 'chat.completion', 'service_tier': None,            │ │
   │                        │ │                              │ 'system_fingerprint': None, 'usage':                │ │
   │                        │ │                              │ {'completion_tokens': 50, 'prompt_tokens': 141,     │ │
   │                        │ │                              │ 'total_tokens': 191}}                               │ │
   │                        │ │ feel_raw_model_response      │ {'id': 'chatcmpl-9pancuOj0pexzspNfMY1K1tqjSTuM',    │ │
   │                        │ │                              │ 'choices': [{'finish_reason': 'stop', 'index': 0,   │ │
   │                        │ │                              │ 'logprobs': None, 'message': {'content':            │ │
   │                        │ │                              │ '```json\n{"answer": "I feel quite concerned about  │ │
   │                        │ │                              │ climate change. It\'s alarming to see the effects   │ │
   │                        │ │                              │ it\'s already having on our planet, from extreme    │ │
   │                        │ │                              │ weather events to the loss of biodiversity. It\'s   │ │
   │                        │ │                              │ something that affects all of us, and I believe     │ │
   │                        │ │                              │ it\'s crucial for both individuals and governments  │ │
   │                        │ │                              │ to take action to mitigate its impacts. The urgency │ │
   │                        │ │                              │ to address this issue is clear, and I hope we can   │ │
   │                        │ │                              │ find sustainable solutions to protect our           │ │
   │                        │ │                              │ environment for future generations."}\n```',        │ │
   │                        │ │                              │ 'role': 'assistant', 'function_call': None,         │ │
   │                        │ │                              │ 'tool_calls': None}}], 'created': 1722083212,       │ │
   │                        │ │                              │ 'model': 'gpt-4-0125-preview', 'object':            │ │
   │                        │ │                              │ 'chat.completion', 'service_tier': None,            │ │
   │                        │ │                              │ 'system_fingerprint': None, 'usage':                │ │
   │                        │ │                              │ {'completion_tokens': 95, 'prompt_tokens': 77,      │ │
   │                        │ │                              │ 'total_tokens': 172}}                               │ │
   │                        │ │ read_raw_model_response      │ {'id': 'chatcmpl-9pance7VWhTUVXSEUXn1N6SA1IwgA',    │ │
   │                        │ │                              │ 'choices': [{'finish_reason': 'stop', 'index': 0,   │ │
   │                        │ │                              │ 'logprobs': None, 'message': {'content':            │ │
   │                        │ │                              │ '{"answer": 0, "comment": "I have read several      │ │
   │                        │ │                              │ books about climate change to better understand its │ │
   │                        │ │                              │ impacts and the science behind it."}', 'role':      │ │
   │                        │ │                              │ 'assistant', 'function_call': None, 'tool_calls':   │ │
   │                        │ │                              │ None}}], 'created': 1722083212, 'model':            │ │
   │                        │ │                              │ 'gpt-4-0125-preview', 'object': 'chat.completion',  │ │
   │                        │ │                              │ 'service_tier': None, 'system_fingerprint': None,   │ │
   │                        │ │                              │ 'usage': {'completion_tokens': 30, 'prompt_tokens': │ │
   │                        │ │                              │ 113, 'total_tokens': 143}}                          │ │
   │                        │ └──────────────────────────────┴─────────────────────────────────────────────────────┘ │
   │ survey                 │ ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
   │                        │ ┃ Questions                                                                          ┃ │
   │                        │ ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩ │
   │                        │ │ ┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓ │ │
   │                        │ │ ┃ Question Name ┃ Question Type ┃ Question Text               ┃ Options          ┃ │ │
   │                        │ │ ┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩ │ │
   │                        │ │ │ important     │ linear_scale  │ How much do you care about  │ 0, 1, 2, 3, 4, 5 │ │ │
   │                        │ │ │               │               │ {{ topic }}?                │                  │ │ │
   │                        │ │ └───────────────┴───────────────┴─────────────────────────────┴──────────────────┘ │ │
   │                        │ │ ┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓   │ │
   │                        │ │ ┃ Question Name ┃ Question Type ┃ Question Text                      ┃ Options ┃   │ │
   │                        │ │ ┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩   │ │
   │                        │ │ │ feel          │ free_text     │ How do you feel about {{ topic }}? │ None    │   │ │
   │                        │ │ └───────────────┴───────────────┴────────────────────────────────────┴─────────┘   │ │
   │                        │ │ ┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓ │ │
   │                        │ │ ┃ Question Name ┃ Question Type ┃ Question Text                        ┃ Options ┃ │ │
   │                        │ │ ┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩ │ │
   │                        │ │ │ read          │ yes_no        │ Have you read any books about {{     │ Yes, No │ │ │
   │                        │ │ │               │               │ topic }}?                            │         │ │ │
   │                        │ │ └───────────────┴───────────────┴──────────────────────────────────────┴─────────┘ │ │
   │                        │ └────────────────────────────────────────────────────────────────────────────────────┘ │
   │ question_to_attributes │ ┏━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
   │                        │ ┃ Attribute ┃ Value                                                                  ┃ │
   │                        │ ┡━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩ │
   │                        │ │ important │ {'question_text': 'How much do you care about {{ topic }}?',           │ │
   │                        │ │           │ 'question_type': 'linear_scale', 'question_options': [0, 1, 2, 3, 4,   │ │
   │                        │ │           │ 5]}                                                                    │ │
   │                        │ │ feel      │ {'question_text': 'How do you feel about {{ topic }}?',                │ │
   │                        │ │           │ 'question_type': 'free_text', 'question_options': None}                │ │
   │                        │ │ read      │ {'question_text': 'Have you read any books about {{ topic }}?',        │ │
   │                        │ │           │ 'question_type': 'yes_no', 'question_options': ['Yes', 'No']}          │ │
   │                        │ └───────────┴────────────────────────────────────────────────────────────────────────┘ │
   └────────────────────────┴────────────────────────────────────────────────────────────────────────────────────────┘


Results columns
^^^^^^^^^^^^^^^
Results contain components that can be accessed and analyzed individually or collectively.
We can see a list of these components by calling the `columns` method:

.. code-block:: python

   results.columns


The following list will be returned for the results generated by the above code:

.. code-block:: text

   ['agent.agent_instruction',
   'agent.agent_name',
   'agent.persona',
   'answer.feel',
   'answer.important',
   'answer.read',
   'comment.important_comment',
   'comment.read_comment',
   'iteration.iteration',
   'model.frequency_penalty',
   'model.logprobs',
   'model.max_tokens',
   'model.model',
   'model.presence_penalty',
   'model.temperature',
   'model.top_logprobs',
   'model.top_p',
   'prompt.feel_system_prompt',
   'prompt.feel_user_prompt',
   'prompt.important_system_prompt',
   'prompt.important_user_prompt',
   'prompt.read_system_prompt',
   'prompt.read_user_prompt',
   'question_options.feel_question_options',
   'question_options.important_question_options',
   'question_options.read_question_options',
   'question_text.feel_question_text',
   'question_text.important_question_text',
   'question_text.read_question_text',
   'question_type.feel_question_type',
   'question_type.important_question_type',
   'question_type.read_question_type',
   'raw_model_response.feel_raw_model_response',
   'raw_model_response.important_raw_model_response',
   'raw_model_response.read_raw_model_response',
   'scenario.topic']


The columns include information about each *agent*, *model* and corresponding *prompts* used to simulate the *answer* to each *question* and *scenario* in the survey, together with each *raw model response*.
If the survey was run multiple times (`run(n=<integer>)`) then the `iteration.iteration` column will show the iteration number for each result.

*Agent* information:

* **agent.agent_name**: This field is always included in any `Results` object. It contains a unique identifier for each `Agent` that can be specified when an agent is is created (`Agent(name=<name>, traits={<traits_dict>})`). If not specified, it is added automatically when results are generated (in the form `Agent_0`, etc.).
* **agent.instruction**: The instruction for the agent. This field is the optional instruction that was passed to the agent when it was created.
* **agent.persona**: Each of the `traits` that we pass to an agent is represented in a column of the results. Our example code created a "persona" trait for each agent, so our results include a "persona" column for this information. Note that the keys for the traits dictionary should be a valid Python keys.

*Answer* information:

* **answer.feel**: Agent responses to the `feel` question.
* **answer.important**: Agent responses to the `important` question.
* **answer.important_comment**: Agent commentary on responses to the `important` question.
A comment field is automatically included for every question in a survey other than free text questions, to allow the agent to optionally provide additional information about its response to the question.

* **answer.read**: Agent responses to the `read` question.
* **answer.read_comment**: Agent commentary on responses to the `read` question.

*Iteration* information:
The `iteration` column shows the number of the run (`run(n=<integer>)`) for the combination of components used (scenarios, agents and models).

*Model* information:
Each of `model` columns is a modifiable parameter of the models used to generate the responses.

* **model.frequency_penalty**: The frequency penalty for the model.
* **model.max_tokens**: The maximum number of tokens for the model.
* **model.model**: The name of the model used.
* **model.presence_penalty**: The presence penalty for the model.
* **model.temperature**: The temperature for the model.
* **model.top_p**: The top p for the model.
* **model.use_cache**: Whether the model uses cache.

*Prompt* information:

* **prompt.feel_system_prompt**: The system prompt for the `feel` question.
* **prompt.feel_user_prompt**: The user prompt for the `feel` question.
* **prompt.important_system_prompt**: The system prompt for the `important` question.
* **prompt.important_user_prompt**: The user prompt for the `important` question.
* **prompt.read_system_prompt**: The system prompt for the `read` question.
* **prompt.read_user_prompt**: The user prompt for the `read` question.
For more details about prompts, please see the :ref:`prompts` section.

*Question* information:

* **question_options.feel_question_options**: The options for the `feel` question, if any.
* **question_options.important_question_options**: The options for the `important` question, if any.
* **question_options.read_question_options**: The options for the `read` question, if any.
* **question_text.feel_question_text**: The text of the `feel` question.
* **question_text.important_question_text**: The text of the `important` question.
* **question_text.read_question_text**: The text of the `read` question.
* **question_type.feel_question_type**: The type of the `feel` question.
* **question_type.important_question_type**: The type of the `important` question.
* **question_type.read_question_type**: The type of the `read` question.

*Raw model response* information:

* **raw_model_response.feel_raw_model_response**: The raw model response for the `feel` question.
* **raw_model_response.important_raw_model_response**: The raw model response for the `important` question.
* **raw_model_response.read_raw_model_response**: The raw model response for the `read` question.

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


The following table will be printed:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━┓
   ┃ model              ┃ agent     ┃ scenario       ┃ answer ┃ answer     ┃
   ┃ .model             ┃ .persona  ┃ .topic         ┃ .read  ┃ .important ┃
   ┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━┩
   │ gpt-4-0125-preview │ student   │ climate change │ Yes    │ 5          │
   ├────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-3.5-turbo      │ student   │ climate change │ Yes    │ 3          │
   ├────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4-0125-preview │ student   │ data privacy   │ Yes    │ 4          │
   ├────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-3.5-turbo      │ student   │ data privacy   │ Yes    │ 4          │
   ├────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4-0125-preview │ celebrity │ climate change │ Yes    │ 5          │
   ├────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-3.5-turbo      │ celebrity │ climate change │ Yes    │ 5          │
   ├────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4-0125-preview │ celebrity │ data privacy   │ Yes    │ 5          │
   ├────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-3.5-turbo      │ celebrity │ data privacy   │ Yes    │ 4          │
   └────────────────────┴───────────┴────────────────┴────────┴────────────┘


Sorting results
^^^^^^^^^^^^^^^
We can sort the columns by calling the `sort_by` method and passing it the column name to sort by:

.. code-block:: python

   (results
   .sort_by("model", reverse=False)
   .select("model", "persona", "topic", "read", "important")
   .print(format="rich")
   )


The following table will be printed:

.. code-block:: text
   
   ┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━┓
   ┃ model              ┃ agent     ┃ scenario       ┃ answer ┃ answer     ┃
   ┃ .model             ┃ .persona  ┃ .topic         ┃ .read  ┃ .important ┃
   ┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━┩
   │ gpt-3.5-turbo      │ student   │ climate change │ Yes    │ 3          │
   ├────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-3.5-turbo      │ student   │ data privacy   │ Yes    │ 4          │
   ├────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-3.5-turbo      │ celebrity │ climate change │ Yes    │ 5          │
   ├────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-3.5-turbo      │ celebrity │ data privacy   │ Yes    │ 4          │
   ├────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4-0125-preview │ student   │ climate change │ Yes    │ 5          │
   ├────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4-0125-preview │ student   │ data privacy   │ Yes    │ 4          │
   ├────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4-0125-preview │ celebrity │ climate change │ Yes    │ 5          │
   ├────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4-0125-preview │ celebrity │ data privacy   │ Yes    │ 5          │
   └────────────────────┴───────────┴────────────────┴────────┴────────────┘


The `sort_by` method can be applied multiple times:

.. code-block:: python

   (results
   .sort_by("model", reverse=False)
   .sort_by("persona", reverse=True)
   .select("model", "persona", "topic", "read", "important")
   .print(format="rich")
   )


The following table will be printed:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━┓
   ┃ model              ┃ agent     ┃ scenario       ┃ answer ┃ answer     ┃
   ┃ .model             ┃ .persona  ┃ .topic         ┃ .read  ┃ .important ┃
   ┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━┩
   │ gpt-3.5-turbo      │ student   │ climate change │ Yes    │ 3          │
   ├────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-3.5-turbo      │ student   │ data privacy   │ Yes    │ 4          │
   ├────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4-0125-preview │ student   │ climate change │ Yes    │ 5          │
   ├────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4-0125-preview │ student   │ data privacy   │ Yes    │ 4          │
   ├────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-3.5-turbo      │ celebrity │ climate change │ Yes    │ 5          │
   ├────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-3.5-turbo      │ celebrity │ data privacy   │ Yes    │ 4          │
   ├────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4-0125-preview │ celebrity │ climate change │ Yes    │ 5          │
   ├────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4-0125-preview │ celebrity │ data privacy   │ Yes    │ 5          │
   └────────────────────┴───────────┴────────────────┴────────┴────────────┘


Labeling results
^^^^^^^^^^^^^^^^
We can also add some table labels by passing a dictionary to the `pretty_labels` argument of the `print` method
(note that we need to include the column prefixes when specifying the table labels, as shown below):

.. code-block:: python

   (results
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
   
   ┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
   ┃                    ┃           ┃                ┃ Have you read any books ┃ How much do you care ┃
   ┃ LLM                ┃ Agent     ┃ Topic          ┃ about {{ topic }}?      ┃ about {{ topic }}?   ┃
   ┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
   │ gpt-3.5-turbo      │ student   │ climate change │ Yes                     │ 3                    │
   ├────────────────────┼───────────┼────────────────┼─────────────────────────┼──────────────────────┤
   │ gpt-3.5-turbo      │ student   │ data privacy   │ Yes                     │ 4                    │
   ├────────────────────┼───────────┼────────────────┼─────────────────────────┼──────────────────────┤
   │ gpt-4-0125-preview │ student   │ climate change │ Yes                     │ 5                    │
   ├────────────────────┼───────────┼────────────────┼─────────────────────────┼──────────────────────┤
   │ gpt-4-0125-preview │ student   │ data privacy   │ Yes                     │ 4                    │
   ├────────────────────┼───────────┼────────────────┼─────────────────────────┼──────────────────────┤
   │ gpt-3.5-turbo      │ celebrity │ climate change │ Yes                     │ 5                    │
   ├────────────────────┼───────────┼────────────────┼─────────────────────────┼──────────────────────┤
   │ gpt-3.5-turbo      │ celebrity │ data privacy   │ Yes                     │ 4                    │
   ├────────────────────┼───────────┼────────────────┼─────────────────────────┼──────────────────────┤
   │ gpt-4-0125-preview │ celebrity │ climate change │ Yes                     │ 5                    │
   ├────────────────────┼───────────┼────────────────┼─────────────────────────┼──────────────────────┤
   │ gpt-4-0125-preview │ celebrity │ data privacy   │ Yes                     │ 5                    │
   └────────────────────┴───────────┴────────────────┴─────────────────────────┴──────────────────────┘


Filtering results
^^^^^^^^^^^^^^^^^
Results can be filtered by using the `filter` method and passing it a logical expression identifying the results that should be selected.
For example, the following code will filter results where the answer to `important` is "5" and then just print the `topic` and `important_comment` columns:

.. code-block:: python

   (results
   .filter("important == 5")
   .select("topic", "important_comment")
   .print(format="rich")
   )


This will return an abbreviated table:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ scenario       ┃ answer                                                                                         ┃
   ┃ .topic         ┃ .important_comment                                                                             ┃
   ┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
   │ climate change │ I believe climate change is one of the most pressing issues of our time, affecting ecosystems, │
   │                │ weather patterns, and global living conditions. It's crucial to address it with urgency to     │
   │                │ ensure a sustainable future for all.                                                           │
   ├────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────┤
   │ climate change │ As a celebrity, I believe I have a responsibility to use my platform to advocate for urgent    │
   │                │ issues, and climate change is one of the most critical challenges we face today. It's          │
   │                │ imperative that we all contribute to solutions and raise awareness to protect our planet for   │
   │                │ future generations.                                                                            │
   ├────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────┤
   │ climate change │ I care deeply about climate change and believe it is crucial for us to take action to protect  │
   │                │ our planet for future generations.                                                             │
   ├────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────┤
   │ data privacy   │ As a celebrity, data privacy is paramount to me. It's not just about protecting personal       │
   │                │ information but also about safeguarding the privacy of my family, friends, and fans. In an era │
   │                │ where information can be easily accessed and shared, taking steps to ensure data privacy is    │
   │                │ crucial. It helps in maintaining personal security and preventing unauthorized access to       │
   │                │ sensitive information.                                                                         │
   └────────────────┴────────────────────────────────────────────────────────────────────────────────────────────────┘


**Note:** The `filter` method allows us to pass the unique short names of the columns (without the prefixes) when specifying the logical expression.
However, because the `model.model` column name is also a prefix, we need to include the prefix when filtering by this column, as shown in the example below:

.. code-block:: python

   (results
   .filter("model.model == 'gpt-4-0125-preview'")
   .select("model", "persona", "topic", "read", "important")
   .print(format="rich")
   )


Limiting results
^^^^^^^^^^^^^^^^
We can select and print a limited number of results by passing the desired number of `max_rows` to the `print()` method.
This can be useful for quickly checking the first few results:

.. code-block:: python

   (results
   .select("model", "persona", "topic", "read", "important")
   .print(max_rows=4, format="rich")
   )


This will return a table of the selected components of the first 4 results:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━┓
   ┃ model              ┃ agent    ┃ scenario       ┃ answer ┃ answer     ┃
   ┃ .model             ┃ .persona ┃ .topic         ┃ .read  ┃ .important ┃
   ┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━┩
   │ gpt-4-0125-preview │ student  │ climate change │ Yes    │ 5          │
   ├────────────────────┼──────────┼────────────────┼────────┼────────────┤
   │ gpt-3.5-turbo      │ student  │ climate change │ Yes    │ 3          │
   ├────────────────────┼──────────┼────────────────┼────────┼────────────┤
   │ gpt-4-0125-preview │ student  │ data privacy   │ Yes    │ 4          │
   ├────────────────────┼──────────┼────────────────┼────────┼────────────┤
   │ gpt-3.5-turbo      │ student  │ data privacy   │ Yes    │ 4          │
   └────────────────────┴──────────┴────────────────┴────────┴────────────┘



Sampling results
^^^^^^^^^^^^^^^^
We can select a sample of `n` results by passing the desired number of random results to the `sample()` method.
This can be useful for checking a random subset of the results with different parameters:

.. code-block:: python

   sample_results = results.sample(2)

   (sample_results
   .sort_by("model", reverse=False)
   .select("model", "persona", "topic", "read", "important")
   .print(format="rich")
   )


This will return a table of the specified number of randomly selected results:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━┓
   ┃ model              ┃ agent    ┃ scenario       ┃ answer ┃ answer     ┃
   ┃ .model             ┃ .persona ┃ .topic         ┃ .read  ┃ .important ┃
   ┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━┩
   │ gpt-3.5-turbo      │ student  │ climate change │ Yes    │ 3          │
   ├────────────────────┼──────────┼────────────────┼────────┼────────────┤
   │ gpt-3.5-turbo      │ student  │ data privacy   │ Yes    │ 4          │
   └────────────────────┴──────────┴────────────────┴────────┴────────────┘



Shuffling results
^^^^^^^^^^^^^^^^^
We can shuffle results by calling the `shuffle()` method.
This can be useful for quickly checking the first few results:

.. code-block:: python

   shuffle_results = results.shuffle()

   (shuffle_results
   .select("model", "persona", "topic", "read", "important")
   .print(format="rich")
   )


This will return a table of shuffled results:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━┓
   ┃ model              ┃ agent     ┃ scenario       ┃ answer ┃ answer     ┃
   ┃ .model             ┃ .persona  ┃ .topic         ┃ .read  ┃ .important ┃
   ┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━┩
   │ gpt-4-0125-preview │ student   │ climate change │ Yes    │ 5          │
   ├────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-3.5-turbo      │ celebrity │ climate change │ Yes    │ 5          │
   ├────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4-0125-preview │ celebrity │ data privacy   │ Yes    │ 5          │
   ├────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-3.5-turbo      │ celebrity │ data privacy   │ Yes    │ 4          │
   ├────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-3.5-turbo      │ student   │ climate change │ Yes    │ 3          │
   ├────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4-0125-preview │ student   │ data privacy   │ Yes    │ 4          │
   ├────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-4-0125-preview │ celebrity │ climate change │ Yes    │ 5          │
   ├────────────────────┼───────────┼────────────────┼────────┼────────────┤
   │ gpt-3.5-turbo      │ student   │ data privacy   │ Yes    │ 4          │
   └────────────────────┴───────────┴────────────────┴────────┴────────────┘



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



Interacting via SQL
^^^^^^^^^^^^^^^^^^^
We can also interact with the results via SQL using the `sql` method.
This is done by passing a SQL query and a `shape` ("long" or "wide") for the resulting table, where the table name in the query is "self".

The "wide" shape will return a table with each result as a row and columns for the selected columns of the results.
For example, the following code will return a table showing the `model`, `persona`, `read` and `important` columns for the first 4 results:

.. code-block:: python

   results.sql("select model, persona, read, important from self limit 4", shape="wide")


This following table will be displayed:

.. code-block:: text

      model	               persona	read	important
   0	gpt-4-0125-preview	student	Yes	5
   1	gpt-3.5-turbo	      student	Yes	3
   2	gpt-4-0125-preview	student	Yes	4
   3	gpt-3.5-turbo	      student	Yes	4


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
   0	0	question_text	important_question_text	How much do you care about {{ topic }}?
   1	0	question_text	feel_question_text	   How do you feel about {{ topic }}?
   2	0	question_text	read_question_text	   Have you read any books about {{ topic }}?
   3	1	question_text	important_question_text	How much do you care about {{ topic }}?
   4	1	question_text	feel_question_text	   How do you feel about {{ topic }}?
   5	1	question_text	read_question_text	   Have you read any books about {{ topic }}?
   6	2	question_text	important_question_text	How much do you care about {{ topic }}?
   7	2	question_text	feel_question_text	   How do you feel about {{ topic }}?
   8	2	question_text	read_question_text	   Have you read any books about {{ topic }}?
   9	3	question_text	important_question_text	How much do you care about {{ topic }}?
   10	3	question_text	feel_question_text	   How do you feel about {{ topic }}?
   11	3	question_text	read_question_text	   Have you read any books about {{ topic }}?
   12	4	question_text	important_question_text	How much do you care about {{ topic }}?
   13	4	question_text	feel_question_text	   How do you feel about {{ topic }}?
   14	4	question_text	read_question_text	   Have you read any books about {{ topic }}?
   15	5	question_text	important_question_text	How much do you care about {{ topic }}?
   16	5	question_text	feel_question_text	   How do you feel about {{ topic }}?
   17	5	question_text	read_question_text	   Have you read any books about {{ topic }}?
   18	6	question_text	important_question_text	How much do you care about {{ topic }}?
   19	6	question_text	feel_question_text	   How do you feel about {{ topic }}?
   20	6	question_text	read_question_text	   Have you read any books about {{ topic }}?
   21	7	question_text	important_question_text	How much do you care about {{ topic }}?
   22	7	question_text	feel_question_text	   How do you feel about {{ topic }}?
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

      model.model	         agent.persona	answer.important
   0	gpt-4-0125-preview	student	      5
   1	gpt-3.5-turbo	      student	      3
   2	gpt-4-0125-preview	student	      4
   3	gpt-3.5-turbo	      student	      4
   4	gpt-4-0125-preview	celebrity	   5
   5	gpt-3.5-turbo	      celebrity	   5
   6	gpt-4-0125-preview	celebrity	   5
   7	gpt-3.5-turbo	      celebrity	   4


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
If any exceptions are raised when the survey is run, the `Results` object will store the exception information.
This can be accessed by calling the `show_exceptions()` method:

.. code-block:: python

   results.show_exceptions()


This will return a table of information about the exceptions that were raised during the survey run.
See the :ref:`exceptions` section for more information on viewing exceptions.



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

