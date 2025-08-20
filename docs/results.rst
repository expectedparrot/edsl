.. _results:

Results
=======

A `Results` object represents the outcome of running a `Survey`. 
It contains a list of individual `Result` objects, where each `Result` corresponds to a response to the survey for a unique combination of `Agent`, `Model`, and `Scenario` objects used with the survey.

For example, if a survey (of one more more questions) is administered to 2 agents and 2 language models (without any scenarios for the questions), the `Results` will contain 4 `Result` objects: one for each combination of agent and model used with the survey. 
If the survey questions are parameterized with 2 scenarios, the `Results` will expand to include 8 `Result` objects, accounting for all combinations of agents, models, and scenarios.


Generating results 
------------------

A `Results` object is not typically instantiated directly, but is returned by calling the `run()` method of a `Survey` after any agents, language models and scenarios are added to it. 

In order to demonstrate how to access and interact with results, we use the following code to generate results for a simple survey.
Note that specifying agent traits, scenarios (question parameter values) and language models is optional, and we include those steps here for illustration purposes.
See the :ref:`agents`, :ref:`scenarios` and :ref:`models` sections for more details on these components.

**Note:** You must store API keys for language models in order to generate results. 
Please see the :ref:`api_keys` section for instructions on activating :ref:`remote_inference` or storing your own API keys for inference service providers.

To construct a survey we start by creating questions:

.. code-block:: python

  from edsl import QuestionLinearScale, QuestionMultipleChoice

  q1 = QuestionLinearScale(
    question_name = "important",
    question_text = "On a scale from 1 to 5, how important to you is {{ scenario.topic }}?",
    question_options = [0, 1, 2, 3, 4, 5],
    option_labels = {0:"Not at all important", 5:"Very important"}
  )

  q2 = QuestionMultipleChoice(
    question_name = "read",
    question_text = "Have you read any books about {{ scenario.topic }}?",
    question_options = ["Yes", "No", "I do not know"]
  )


We combine them in a survey to administer them together:

.. code-block:: python

  from edsl import Survey

  survey = Survey([q1, q2])


We have parameterized our questions, so we can use them with different scenarios: 

.. code-block:: python

  from edsl import ScenarioList

  scenarios = ScenarioList.from_list("topic", ["climate change", "house prices"])


We can optionally create agents with personas or other relevant traits to answer the survey:

.. code-block:: python

  from edsl import AgentList, Agent

  agents = AgentList(
    Agent(traits = {"persona": p}) for p in ["student", "celebrity"]
  )


We can specify the language models that we want to use to generate responses:

.. code-block:: python

  from edsl import ModelList, Model

  models = ModelList(
    Model(m) for m in ["gemini-1.5-flash", "gpt-4o"]
  )


Finally, we generate results by adding the scenarios, agents and models to the survey and calling the `run()` method:

.. code-block:: python

  results = survey.by(scenarios).by(agents).by(models).run()


For more details on each of the above steps, please see the :ref:`agents`, :ref:`scenarios` and :ref:`models` sections of the docs.


Result objects 
--------------

We can check the number of `Result` objects created by inspecting the length of the `Results`:

.. code-block:: python

  len(results)

This will count 2 (scenarios) x 2 (agents) x 2 (models) = 8 `Result` objects:

.. code-block:: text

  8


Generating multiple results
---------------------------

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


Output:

.. list-table::
  :header-rows: 1

  * - key
    - value
  * - agent:traits
    - {'persona': 'student'}
  * - scenario:topic
    - climate change
  * - scenario:scenario_index
    - 0
  * - model:model
    - gemini-1.5-flash
  * - model:parameters
    - {'temperature': 0.5, 'topP': 1, 'topK': 1, 'maxOutputTokens': 2048, 'stopSequences': []}
  * - model:inference_service
    - google
  * - iteration
    - 0
  * - answer:important
    - 5
  * - answer:read
    - Yes
  * - prompt:important_user_prompt
    - {'text': 'On a scale from 1 to 5, how important to you is climate change?\n\n0 : Not at all important\n\n1 : \n\n2 : \n\n3 : \n\n4 : \n\n5 : Very important\n\nOnly 1 option may be selected.\n\nRespond only with the code corresponding to one of the options. E.g., "1" or "5" by itself.\n\nAfter the answer, you can put a comment explaining why you chose that option on the next line.', 'class_name': 'Prompt'}
  * - prompt:important_system_prompt
    - {'text': "You are answering questions as if you were a human. Do not break character. Your traits: {'persona': 'student'}", 'class_name': 'Prompt'}
  * - prompt:read_user_prompt
    - {'text': '\nHave you read any books about climate change?\n\n    \nYes\n    \nNo\n    \nI do not know\n    \n\nOnly 1 option may be selected.\n\nRespond only with a string corresponding to one of the options.\n\n\nAfter the answer, you can put a comment explaining why you chose that option on the next line.', 'class_name': 'Prompt'}
  * - prompt:read_system_prompt
    - {'text': "You are answering questions as if you were a human. Do not break character. Your traits: {'persona': 'student'}", 'class_name': 'Prompt'}
  * - raw_model_response:important_raw_model_response
    - {'candidates': [{'content': {'parts': [{'text': "5\n\nIt's, like, a huge deal!  The future of the planet is at stake, and that affects everything –  from the environment to the economy to, you know, my future.  It's definitely something I worry about.\n"}], 'role': 'model'}, 'finish_reason': 1, 'safety_ratings': [{'category': 8, 'probability': 1, 'blocked': False}, {'category': 10, 'probability': 1, 'blocked': False}, {'category': 7, 'probability': 1, 'blocked': False}, {'category': 9, 'probability': 1, 'blocked': False}], 'avg_logprobs': -0.2145003372768186, 'token_count': 0, 'grounding_attributions': []}], 'usage_metadata': {'prompt_token_count': 128, 'candidates_token_count': 53, 'total_token_count': 181, 'cached_content_token_count': 0}, 'model_version': 'gemini-1.5-flash'}
  * - raw_model_response:important_input_tokens
    - 128
  * - raw_model_response:important_output_tokens
    - 53
  * - raw_model_response:important_input_price_per_million_tokens
    - 0.075000
  * - raw_model_response:important_output_price_per_million_tokens
    - 0.300000
  * - raw_model_response:important_cost
    - 0.000025
  * - raw_model_response:important_one_usd_buys
    - 39215.691903
  * - raw_model_response:read_raw_model_response
    - {'candidates': [{'content': {'parts': [{'text': "Yes\n\nI've read a few articles and some chapters from textbooks for my environmental science classes, which covered climate change extensively.  It's not quite the same as reading a whole book dedicated to the topic, but I've definitely learned about it.\n"}], 'role': 'model'}, 'finish_reason': 1, 'safety_ratings': [{'category': 8, 'probability': 1, 'blocked': False}, {'category': 10, 'probability': 1, 'blocked': False}, {'category': 7, 'probability': 1, 'blocked': False}, {'category': 9, 'probability': 1, 'blocked': False}], 'avg_logprobs': -0.15844399840743453, 'token_count': 0, 'grounding_attributions': []}], 'usage_metadata': {'prompt_token_count': 95, 'candidates_token_count': 54, 'total_token_count': 149, 'cached_content_token_count': 0}, 'model_version': 'gemini-1.5-flash'}
  * - raw_model_response:read_input_tokens
    - 95
  * - raw_model_response:read_output_tokens
    - 54
  * - raw_model_response:read_input_price_per_million_tokens
    - 0.075000
  * - raw_model_response:read_output_price_per_million_tokens
    - 0.300000
  * - raw_model_response:read_cost
    - 0.000023
  * - raw_model_response:read_one_usd_buys
    - 42872.461058
  * - question_to_attributes:important
    - {'question_text': 'On a scale from 1 to 5, how important to you is {{ topic }}?', 'question_type': 'linear_scale', 'question_options': [0, 1, 2, 3, 4, 5]}
  * - question_to_attributes:read
    - {'question_text': 'Have you read any books about {{ topic }}?', 'question_type': 'multiple_choice', 'question_options': ['Yes', 'No', 'I do not know']}
  * - generated_tokens:important_generated_tokens
    - 5 
    
      It's, like, a huge deal!  The future of the planet is at stake, and that affects everything –  from the environment to the economy to, you know, my future.  It's definitely something I worry about.
  * - generated_tokens:read_generated_tokens
    - Yes 
    
      I've read a few articles and some chapters from textbooks for my environmental science classes, which covered climate change extensively.  It's not quite the same as reading a whole book dedicated to the topic, but I've definitely learned about it.
  * - comments_dict:important_comment
    - It's, like, a huge deal!  The future of the planet is at stake, and that affects everything –  from the environment to the economy to, you know, my future.  It's definitely something I worry about.
  * - comments_dict:read_comment
    - I've read a few articles and some chapters from textbooks for my environmental science classes, which covered climate change extensively.  It's not quite the same as reading a whole book dedicated to the topic, but I've definitely learned about it.
  * - cache_keys:important	
    - 98d6961d0529335b74f2363ba9b7a8de
  * - cache_keys:read	
    - 12af825953d89c1f776bd3af40e37cfb
  * - cache_used:important
    - False
  * - cache_used:read
    - False
  * indices:agent
    - 0
  * indices:model
    - 0
  * indices:scenario
    - 0
  * interview_hash
    - 1563541154566694327
  * order
    - 0
  


Results components
------------------

Results contain components that can be accessed and analyzed individually or collectively.
We can see a list of these components by calling the `columns` method:

.. code-block:: python

  results.columns


The following list will be returned for the results generated by the above code:

.. list-table::

  * - agent.agent_index
    - agent.agent_instruction                        
    - agent.agent_name                               
    - agent.persona                                  
    - answer.important                               
    - answer.read 
    - cache_keys.important_cache_key                               
    - cache_keys.read_cache_key
    - cache_keys.important_cache_used                               
    - cache_keys.read_cache_used                                     
    - comment.important_comment                      
    - comment.read_comment                           
    - generated_tokens.important_generated_tokens    
    - generated_tokens.read_generated_tokens         
    - iteration.iteration                            
    - model.frequency_penalty                        
    - model.logprobs  
    - model.maxOutputTokens                               
    - model.max_tokens                               
    - model.model                                    
    - model.presence_penalty  
    - model.stopSequences                       
    - model.temperature
    - model.topK     
    - model.topP                         
    - model.top_logprobs                             
    - model.top_p                                    
    - prompt.important_system_prompt                 
    - prompt.important_user_prompt                   
    - prompt.read_system_prompt                      
    - prompt.read_user_prompt                        
    - question_options.important_question_options    
    - question_options.read_question_options         
    - question_text.important_question_text          
    - question_text.read_question_text               
    - question_type.important_question_type          
    - question_type.read_question_type               
    - raw_model_response.important_cost              
    - raw_model_response.important_input_price_per_million_tokens
    - raw_model_response.important_input_tokens
    - raw_model_response.important_one_usd_buys
    - raw_model_response.important_output_price_per_million_tokens
    - raw_model_response.important_output_tokens      
    - raw_model_response.important_raw_model_response
    - raw_model_response.read_cost                   
    - raw_model_response.read_input_price_per_million_tokens
    - raw_model_response.read_input_tokens
    - raw_model_response.read_one_usd_buys     
    - raw_model_response.read_output_price_per_million_tokens
    - raw_model_response.read_output_tokens      
    - raw_model_response.read_raw_model_response   
    - scenario.scenario_index  
    - scenario.topic                                 


The columns include information about each *agent*, *model* and corresponding *prompts* used to simulate the *answer* to each *question* and *scenario* in the survey, together with each *raw model response*.
If the survey was run multiple times (`run(n=<integer>)`) then the `iteration.iteration` column will show the iteration number for each result.

*Agent* information:

* **agent.agent_index**: The index of the agent in the `AgentList` used to create the survey.
* **agent.instruction**: The instruction for the agent. This field is the optional instruction that was passed to the agent when it was created.
* **agent.agent_name**: This field is always included in any `Results` object. It contains a unique identifier for each `Agent` that can be specified when an agent is is created (`Agent(name=<name>, traits={<traits_dict>})`). If not specified, it is added automatically when results are generated (in the form `Agent_0`, etc.).
* **agent.persona**: Each of the `traits` that we pass to an agent is represented in a column of the results. Our example code created a "persona" trait for each agent, so our results include a "persona" column for this information. Note that the keys for the traits dictionary should be a valid Python keys.

*Answer* information:

* **answer.important**: Agent responses to the linear scale `important` question.
* **answer.read**: Agent responses to the multiple choice `read` question.

*Cache* information:

* **cache_keys.important_cache_key**: The cache key for the `important` question.
* **cache_keys.important_cache_used**: Whether the existing cache was used for the `important` question.
* **cache_keys.read_cache_key**: The cache key for the `read` question.
* **cache_keys.read_cache_used**: Whether the existing cache was used for the `read` question.

*Comment* information:

A "comment" field is automatically included for every question in a survey other than free text questions, to allow the model to provide additional information about its response.
The default instruction for the agent to provide a comment is included in `user_prompt` for a question, and can be modified or omitted when creating the question.
(See the :ref:`prompts` section for details on modifying user and system prompts, and information about prompts in results below. Comments can also be automatically excluded by passing a parameter `include_comment=False` a question when creating it.)

* **comment.important_comment**: Agent commentary on responses to the `important` question.
* **comment.read_comment**: Agent commentary on responses to the `read` question.

*Generated tokens* information:

* **generated_tokens.important_generated_tokens**: The generated tokens for the `important` question.
* **generated_tokens.read_generated_tokens**: The generated tokens for the `read` question.

*Iteration* information:

The `iteration` column shows the number of the run (`run(n=<integer>)`) for the combination of components used (scenarios, agents and models).

*Model* information:

Each of `model` columns is a modifiable parameter of the models used to generate the responses.

* **model.frequency_penalty**: The frequency penalty for the model.
* **model.logprobs**: The logprobs for the model.
* **model.maxOutputTokens**: The maximum number of output tokens for the model.
* **model.max_tokens**: The maximum number of tokens for the model.
* **model.model**: The name of the model used.
* **model.presence_penalty**: The presence penalty for the model.
* **model.stopSequences**: The stop sequences for the model.
* **model.temperature**: The temperature for the model.
* **model.topK**: The top k for the model.
* **model.topP**: The top p for the model.
* **model.top_logprobs**: The top logprobs for the model.
* **model.top_p**: The top p for the model.
* **model.use_cache**: Whether the model uses cache.

*Note:* Some of the above fields are particular to specific models, and may have different names (e.g., `top_p` vs. `topP`).

*Prompt* information:

* **prompt.important_system_prompt**: The system prompt for the `important` question.
* **prompt.important_user_prompt**: The user prompt for the `important` question.
* **prompt.read_system_prompt**: The system prompt for the `read` question.
* **prompt.read_user_prompt**: The user prompt for the `read` question.
For more details about prompts, please see the :ref:`prompts` section.

*Question* information:

* **question_options.important_question_options**: The options for the `important` question, if any.
* **question_options.read_question_options**: The options for the `read` question, if any.
* **question_text.important_question_text**: The text of the `important` question.
* **question_text.read_question_text**: The text of the `read` question.
* **question_type.important_question_type**: The type of the `important` question.
* **question_type.read_question_type**: The type of the `read` question.

*Raw model response* information:

* **raw_model_response.important_cost**: The cost of the result for the `important` question, applying the token quanities & prices.
* **raw_model_response.important_input_price_per_million_tokenss**: The price per million input tokens for the `important` question for the relevant model.
* **raw_model_response.important_input_tokens**: The number of input tokens for the `important` question for the relevant model.
* **raw_model_response.important_one_usd_buys**: The number of identical results for the `important` question that 1USD would cover. 
* **raw_model_response.important_output_price_per_million_tokens**: The price per million output tokens for the `important` question for the relevant model.
* **raw_model_response.important_output_tokens**: The number of output tokens for the `important` question for the relevant model.
* **raw_model_response.important_raw_model_response**: The raw model response for the `important` question.
* **raw_model_response.read_cost**: The cost of the result for the `read` question, applying the token quanities & prices.
* **raw_model_response.read_input_price_per_million_tokens**: The price per million input tokens for the `read` question for the relevant model.
* **raw_model_response.read_input_tokens**: The number of input tokens for the `read` question for the relevant model.
* **raw_model_response.read_one_usd_buys**: The number of identical results for the `read` question that 1USD would cover.
* **raw_model_response.read_output_price_per_million_tokens**: The price per million output tokens for the `read` question for the relevant model.
* **raw_model_response.read_output_tokens**: The number of output tokens for the `read` question for the relevant model.
* **raw_model_response.read_raw_model_response**: The raw model response for the `read` question.

Note that the cost of a result for a question is specific to the components (scenario, agent, model used with it). 

*Scenario* information:

* **scenario.scenario_index**: The index of the scenario.
* **scenario.topic**: The values provided for the "topic" scenario for the questions.

*Note*: We recently added support for OpenAI reasoning models. See an example notebook for usage `here <https://www.expectedparrot.com/content/RobinHorton/reasoning-model-example>`_.
The `Results` that are generated with reasoning models include additional fields for reasoning summaries.


Creating tables by selecting columns
------------------------------------

Each of these columns can be accessed directly by calling the `select()` method and passing the column names.
Alternatively, we can specify the columns to exclude by calling the `drop()` method.
These methods can be chained together to display the specified columns in a table format.

For example, the following code will print a table showing the answers for `read` and `important` together with `model`, `persona` and `topic` columns
(because the column names are unique we can drop the `model`, `agent`, `scenario` and `answer` prefixes when selecting them):

.. code-block:: python

  results = survey.by(scenarios).by(agents).by(models).run() # Running the survey once
  results.select("model", "persona", "topic", "read", "important")


A table with the selected columns will be printed:

.. list-table::
  :header-rows: 1

  * - model.model
    - agent.persona
    - scenario.topic
    - answer.read
    - answer.important
  * - gemini-1.5-flash
    - student
    - climate change
    - Yes
    - 5
  * - gpt-4o
    - student
    - climate change
    - Yes
    - 5
  * - gemini-1.5-flash
    - student
    - house prices
    - No
    - 1
  * - gpt-4o
    - student
    - house prices
    - No
    - 3
  * - gemini-1.5-flash
    - celebrity
    - climate change
    - Yes
    - 5
  * - gpt-4o
    - celebrity
    - climate change
    - Yes
    - 5
  * - gemini-1.5-flash
    - celebrity
    - house prices
    - Yes
    - 3
  * - gpt-4o
    - celebrity
    - house prices
    - No
    - 3


Sorting results
---------------

We can sort the columns by calling the `sort_by` method and passing it the column names to sort by:

.. code-block:: python

  (
    results
    .sort_by("model", "persona", reverse=False)
    .select("model", "persona", "topic", "read", "important")
  )


The following table will be printed:

.. list-table::
  :header-rows: 1

  * - model.model
    - agent.persona
    - scenario.topic
    - answer.read
    - answer.important
  * - gemini-1.5-flash
    - celebrity
    - climate change
    - Yes
    - 5
  * - gemini-1.5-flash
    - celebrity
    - house prices
    - Yes
    - 3
  * - gemini-1.5-flash
    - student
    - climate change
    - Yes
    - 5
  * - gemini-1.5-flash
    - student
    - house prices
    - No
    - 1
  * - gpt-4o
    - celebrity
    - climate change
    - Yes
    - 5
  * - gpt-4o
    - celebrity
    - house prices
    - No
    - 3
  * - gpt-4o
    - student
    - climate change
    - Yes
    - 5
  * - gpt-4o
    - student
    - house prices
    - No
    - 3


Labeling results
----------------

We can also add some table labels by passing a dictionary to the `pretty_labels` argument of the `print` method
(note that we need to include the column prefixes when specifying the table labels, as shown below):

.. code-block:: python

  (
    results
    .sort_by("model", "persona", reverse=True)
    .select("model", "persona", "topic", "read", "important")
    .print(pretty_labels={
        "model.model": "LLM", 
        "agent.persona": "Agent", 
        "scenario.topic": "Topic", 
        "answer.read": q2.question_text,
        "answer.important": q1.question_text
        }, format="rich")
  )


The following table will be printed:

.. list-table::
  :header-rows: 1

  * - LLM
    - Agent
    - Topic
    - Have you read any books about {{ scenario.topic }}?
    - On a scale from 1 to 5, how important to you is {{ scenario.topic }}?
  * - gpt-4o
    - student
    - climate change
    - Yes
    - 5
  * - gpt-4o
    - student
    - house prices
    - No
    - 3
  * - gpt-4o
    - celebrity
    - climate change
    - Yes
    - 5
  * - gpt-4o
    - celebrity
    - house prices
    - No
    - 3
  * - gemini-1.5-flash
    - student
    - climate change
    - Yes
    - 5
  * - gemini-1.5-flash
    - student
    - house prices
    - No
    - 1
  * - gemini-1.5-flash
    - celebrity
    - climate change
    - Yes
    - 5
  * - gemini-1.5-flash
    - celebrity
    - house prices
    - Yes
    - 3


Filtering results
-----------------

Results can be filtered by using the `filter` method and passing it a logical expression identifying the results that should be selected.
For example, the following code will filter results where the answer to `important` is "5" and then just print the `topic` and `important_comment` columns:

.. code-block:: python

  (
    results
    .filter("important == 5")
    .select("topic", "important", "important_comment")
  )


This will return an abbreviated table:

.. list-table::
  :header-rows: 1

  * - scenario.topic
    - answer.important
    - comment.important_comment
  * - climate change
    - 5
    - It's, like, a huge deal. The future of the planet is at stake, and that affects everything - from the environment to the economy to social justice. It's something I worry about a lot.
  * - climate change
    - 5
    - As a student, I'm really concerned about climate change because it affects our future and the planet we'll inherit. It's crucial to understand and address it to ensure a sustainable world for generations to come.
  * - climate change
    - 5
    - It's a huge issue, you know? We only have one planet, and if we don't take care of it, what kind of world are we leaving for future generations? It's not just about polar bears; it's about everything. It's my responsibility, as someone with a platform, to speak out about it.
  * - climate change
    - 5
    - Climate change is a critical issue that affects everyone globally, and as a public figure, I believe it's important to use my platform to raise awareness and advocate for sustainable practices.


**Note:** The `filter` method allows us to pass the unique short names of the columns (without the prefixes) when specifying the logical expression.
However, because the `model.model` column name is also a prefix, we need to include the prefix when filtering by this column, as shown in the example below:

.. code-block:: python

  (
    results
    .filter("model.model == 'gpt-4o'")
    .select("model", "persona", "topic", "read", "important")
  )


This will return a table of results where the model is "gpt-4o":

.. list-table::
  :header-rows: 1

  * - model.model
    - agent.persona
    - scenario.topic
    - answer.read
    - answer.important
  * - gpt-4o
    - student
    - climate change
    - Yes
    - 5
  * - gpt-4o
    - student
    - house prices
    - No
    - 3
  * - gpt-4o
    - celebrity
    - climate change
    - Yes
    - 5
  * - gpt-4o
    - celebrity
    - house prices
    - No
    - 3


Limiting results
----------------

We can select and print a limited number of results by passing the desired number of `max_rows` to the `print()` method.
This can be useful for quickly checking the first few results:

.. code-block:: python

  (
    results
    .select("model", "persona", "topic", "read", "important")
    .print(max_rows=4, format="rich")
  )


This will return a table of the selected components of the first 4 results:

.. list-table::
  :header-rows: 1

  * - model.model
    - agent.persona
    - scenario.topic
    - answer.read
    - answer.important
  * - gemini-1.5-flash
    - student
    - climate change
    - Yes
    - 5
  * - gpt-4o
    - student
    - climate change
    - Yes
    - 5
  * - gemini-1.5-flash
    - student
    - house prices
    - No
    - 1
  * - gpt-4o
    - student
    - house prices
    - No
    - 3


Sampling results
----------------

We can select a sample of `n` results by passing the desired number of random results to the `sample()` method.
This can be useful for checking a random subset of the results with different parameters:

.. code-block:: python

  sample_results = results.sample(2)

  (
    sample_results
    .sort_by("model")
    .select("model", "persona", "topic", "read", "important")
  )


This will return a table of the specified number of randomly selected results:

.. list-table::
  :header-rows: 1

  * - model.model
    - agent.persona
    - scenario.topic
    - answer.read
    - answer.important
  * - gpt-4o
    - celebrity
    - house prices
    - No
    - 3
  * - gpt-4o
    - celebrity
    - climate change
    - Yes
    - 5


Shuffling results
-----------------

We can shuffle results by calling the `shuffle()` method.
This can be useful for quickly checking the first few results:

.. code-block:: python

  shuffle_results = results.shuffle()

  (
    shuffle_results
    .select("model", "persona", "topic", "read", "important")
  )


This will return a table of shuffled results:

.. list-table::
  :header-rows: 1

  * - model.model
    - agent.persona
    - scenario.topic
    - answer.read
    - answer.important
  * - gemini-1.5-flash
    - celebrity
    - climate change
    - Yes
    - 5
  * - gpt-4o
    - student
    - house prices
    - No
    - 3
  * - gemini-1.5-flash
    - celebrity
    - house prices
    - Yes
    - 3
  * - gemini-1.5-flash
    - student
    - house prices
    - No
    - 1
  * - gpt-4o
    - celebrity
    - house prices
    - No
    - 3
  * - gpt-4o
    - celebrity
    - climate change
    - Yes
    - 5
  * - gpt-4o
    - student
    - climate change
    - Yes
    - 5
  * - gemini-1.5-flash
    - student
    - climate change
    - Yes
    - 5


Adding results
--------------

We can add results together straightforwardly by using the `+` operator:

.. code-block:: python

  add_results = results + results


We can see that the results have doubled:

.. code-block:: text

  len(add_results)


This will return the number of results:

.. code-block:: text

  16

   

Flattening results
------------------

If a field of results contains dictionaries we can flatten them into separate fields by calling the `flatten()` method. 
This method takes a list of the fields to flatten and a boolean indicator whether to preserve the original fields in the new `Results` object that is returned.

For example:

.. code-block:: python

 from edsl import QuestionDict, Model

  m = Model("gemini-1.5-flash")

  q = QuestionDict(
    question_name = "recipe",
    question_text = "Please provide a simple recipe for hot chocolate.",
    answer_keys = ["title", "ingredients", "instructions"]
  )

  r = q.by(m).run()

  r.select("model", "recipe").flatten(field="answer.recipe", keep_original=True)


This will return a table of the flattened results:

.. list-table::
  :header-rows: 1

  * - model.model
    - answer.recipe
    - answer.recipe.title
    - answer.recipe.ingredients
    - answer.recipe.instructions
  * - gemini-1.5-flash
    - {'title': 'Simple Hot Chocolate', 'ingredients': ['1 cup milk (dairy or non-dairy)', '1 tablespoon unsweetened cocoa powder', '1-2 tablespoons sugar (or to taste)', 'Pinch of salt'], 'instructions': ['Combine milk, cocoa powder, sugar, and salt in a small saucepan.', 'Heat over medium heat, stirring constantly, until the mixture is smooth and heated through.', 'Do not boil.', 'Pour into a mug and enjoy!']}
    - Simple Hot Chocolate 
    - ['1 cup milk (dairy or non-dairy)', '1 tablespoon unsweetened cocoa powder', '1-2 tablespoons sugar (or to taste)', 'Pinch of salt']
    - ['Combine milk, cocoa powder, sugar, and salt in a small saucepan.', 'Heat over medium heat, stirring constantly, until the mixture is smooth and heated through.', 'Do not boil.', 'Pour into a mug and enjoy!']


Retrieving results 
------------------

We can retrieve details about results posted to Coop by calling the `list()` method on the `Results` class.
For example, the following code will return information about the 10 most recent results posted to Coop:

.. code-block:: python

  from edsl import Results

  results = Results.list()


The following information will be returned:

.. list-table::
  :header-rows: 1

  * - Column
    - Description
  * - last_updated_ts
    - The timestamp when the result was last updated.
  * - alias
    - The alias for the results.
  * - uuid
    - The UUID of the results.
  * - version
    - The version of the result.
  * - created_ts
    - The timestamp when the results were created.
  * - visibility
    - The visibility of the results (public, private or unlisted).
  * - description
    - A description of the results, if any.
  * - url
    - The URL to access the results.
  * - object_type
    - The type of object (e.g., Results).
  * - owner_username
    - The username of the owner of the results.
  * - alias_url
    - The URL for the alias, if any.


To access the next page of results, you can specify the page= parameter:

.. code-block:: python

  results = Results.list(page=2)


This will return the next page of results, with the same columns as above.

.. code-block:: python

  from edsl import Results

  # Retrieve the first 2 pages of results and collect their UUIDs
  uuids = []
  for i in range(1, 3):
    results = Results.list(page=i)
    uuids.extend(list(results.to_key_value("uuid")))


If you have a predetermined number of objects, you can also use page_size= to specify the number of objects per page (up to 100 objects):

.. code-block:: python

  results = Results.list(page_size=5)


This will return the first 5 results, with the same columns as above.

By default, the most recently created objects are returned first. You can reverse this by specifying sort_ascending=True:

.. code-block:: python

  from edsl import Results

  # Retrieve the first 10 results, sorted in ascending order by creation time
  results = Results.list(sort_ascending=True)


You can also filter objects by description using the search_query parameter:

.. code-block:: python

  from edsl import Results

  # Retrieve results with a description containing the word "testing"
  results = Results.list(search_query="testing")


If you want not just the metadata, but the actual object, you can call .fetch() on the metadata list:

.. code-block:: python

  from edsl import Results

  # Retrieve the first 10 results and fetch the actual objects
  results = Results.list().fetch()


The `list()` method can also be called on `Agent` and `Jobs` objects, and the `Coop` client object (to retrieve details of objects of any type).


Generating a report
-------------------

We can create a report of the results by calling the `report()` method and passing the columns to be included (all columns are included by default).
This generates a report in markdown by iterating through the rows, presented as observations. 
You can optionally pass headers, a divider and a limit on the number of observations to include. 
It can be useful if you want to display some sample part of larger results in a working notebook you are sharing.

For example, the following code will generate a report of the first 4 results:

.. code-block:: python

  from edsl import QuestionFreeText, ScenarioList, Model

  m = Model("gemini-1.5-flash")

  s = ScenarioList.from_list("language", ["German", "Dutch", "French", "English"])

  q = QuestionFreeText(
    question_name = "poem",
    question_text = "Please write me a short poem about winter in {{ language }}."
  )

  r = q.by(s).by(m).run()

  r.select("model", "poem", "language").report(top_n=2, divider=False, return_string=True)


This will return a report of the first 2 results:

.. code-block:: text

  Observation: 1

  model.model
  gemini-1.5-flash

  answer.poem
  Der Schnee fällt leis', ein weicher Flor, Die Welt in Weiß, ein Zauberchor. Die Bäume stehn, in Stille gehüllt, Der Winterwind, sein Lied erfüllt.

  (Translation: The snow falls softly, a gentle veil, / The world in white, a magic choir. / The trees stand, wrapped in silence, / The winter wind, its song fulfilled.)

  scenario.language
  German

  Observation: 2
  model.model
  gemini-1.5-flash

  answer.poem
  De winter komt, de dagen kort, De sneeuw valt zacht, een wit decor. De bomen staan, kaal en stil, Een ijzige wind, een koude tril.

  (Translation: Winter comes, the days are short, / The snow falls softly, a white décor. / The trees stand, bare and still, / An icy wind, a cold shiver.)

  scenario.language
  Dutch

  "# Observation: 1\n## model.model\ngemini-1.5-flash\n## answer.poem\nDer Schnee fällt leis', ein weicher Flor,\nDie Welt in Weiß, ein Zauberchor.\nDie Bäume stehn, in Stille gehüllt,\nDer Winterwind, sein Lied erfüllt.\n\n(Translation: The snow falls softly, a gentle veil, / The world in white, a magic choir. / The trees stand, wrapped in silence, / The winter wind, its song fulfilled.)\n## scenario.language\nGerman\n\n---\n\n# Observation: 2\n## model.model\ngemini-1.5-flash\n## answer.poem\nDe winter komt, de dagen kort,\nDe sneeuw valt zacht, een wit decor.\nDe bomen staan, kaal en stil,\nEen ijzige wind, een koude tril.\n\n(Translation: Winter comes, the days are short, / The snow falls softly, a white décor. / The trees stand, bare and still, / An icy wind, a cold shiver.)\n## scenario.language\nDutch\n"


Accessing results with SQL
--------------------------

We can interact with results via SQL using the `sql` method.
This is done by passing a SQL query and a `shape` ("long" or "wide") for the resulting table, where the table name in the query is "self".

For example, the following code will return a table showing the `model`, `persona`, `read` and `important` columns for the first 4 results:

.. code-block:: python

  results.sql("select model, persona, read, important from self limit 4")


This following table will be displayed

.. list-table::
  :header-rows: 1

  * - model
    - persona
    - read
    - important
  * - gemini-1.5-flash
    - student
    - Yes
    - 5
  * - gpt-4o
    - student
    - Yes
    - 5
  * - gemini-1.5-flash
    - student
    - No
    - 1
  * - gpt-4o
    - student
    - No
    - 3


Dataframes
----------

We can also export results to other formats.
The `to_pandas` method will turn our results into a Pandas dataframe:

.. code-block:: python

  results.to_pandas()


For example, here we use it to create a dataframe consisting of the models, personas and the answers to the `important` question:

.. code-block:: python

  results.to_pandas()[["model.model", "agent.persona", "answer.important"]]



Exporting to CSV or JSON
------------------------

The `to_csv` method will write the results to a CSV file:

.. code-block:: python

  results.to_pandas().to_csv("results.csv")


The `to_json` method will write the results to a JSON file:

.. code-block:: python

  results.to_pandas().to_json("results.json")


Revising prompts to improve results
-----------------------------------

If any of your results are missing model responses, you can use the `spot_issues()` method to help identify the issues and then revise the prompts to improve the results.
This method runs a meta-survey of (2) questions for any prompts that generated a bad or null response, and then returns the results of the meta-survey.

The first question in the survey is a `QuestionFreeText` question which prompts the model to describe the likely issues with the prompts:

.. code-block:: text

  The following prompts generated a bad or null response: '{{ original_prompts }}' 
  What do you think was the likely issue(s)?


The second question in the survey is a `QuestionDict` question which prompts the model to return a dictionary consisting of revised user and system prompts:

.. code-block:: text

  The following prompts generated a bad or null response: '{{ original_prompts }}' 
  You identified the issue(s) as '{{ issues.answer }}'. 
  Please revise the prompts to address the issue(s).


You can optionally pass a list of models to use with the meta-survey, instead of the default model.

Example usage:

.. code-block:: python

  # Returns a Results object with the results of the meta-survey
  results.spot_issues(models=["gpt-4o"])

  # You can inspect the metadata for your original prompts together with the results of the meta-survey
  results.select(
    "original_question", # The name of the question that generated a bad or null response
    "original_agent_index", # The index of the agent that generated a bad or null response
    "original_scenario_index", # The index of the scenario that generated a bad or null response
    "original_prompts", # The original prompts that generated a bad or null response
    "answer.issues", # Free text description of potential issues in the original prompts
    "answer.revised" # A dictionary of revised user and system prompts
  )


See an `example of the method <https://www.expectedparrot.com/content/385734e7-7767-4464-9ebd-0b009dd2e15f>`_.


Exceptions
----------

If any exceptions are raised when the survey is run a detailed exceptions report is generated and can be opened in your browser.
See the :ref:`exceptions` section for more information on exceptions.



Result class
------------

.. autoclass:: edsl.results.Result
   :members:  
   :inherited-members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Results class
-------------

.. autoclass:: edsl.results.Results
   :members:
   :inherited-members:
   :exclude-members: append, clear, copy, count, extend, index, insert, pop, remove, reverse, sort, known_data_types, Mixins, main, PromptDict
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

