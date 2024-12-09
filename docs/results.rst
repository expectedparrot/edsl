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
      Model(m) for m in ["gemma-7b-it", "gpt-4o"]
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


Output:

.. list-table::
   :header-rows: 1

   * - key
     - value
   * - agent:traits
     - {'persona': 'student'}
   * - scenario:topic
     - climate change
   * - model:model
     - gemma-7b-it
   * - model:parameters
     - {'temperature': 0.5, 'max_tokens': 1000, 'top_p': 1, 'frequency_penalty': 0, 'presence_penalty': 0, 'logprobs': False, 'top_logprobs': 3}
   * - iteration
     - 0
   * - answer:important
     - 5
   * - answer:opinions
     - Climate change is an urgent and complex issue that demands immediate attention. The overwhelming scientific consensus points towards human activities as the primary drivers of global warming and its devastating consequences.

       The effects of climate change are undeniable. Rising global temperatures, melting glaciers, extreme weather events, and rising sea levels are just some of the devastating impacts we are witnessing. These changes have far-reaching consequences for human societies and ecosystems.

       I believe it is crucial for us to take decisive action to mitigate climate change and adapt to its effects. This requires a concerted global effort involving governments, businesses, and individuals.

       **Key concerns:**
       * The unprecedented rate and magnitude of climate change
       * The irreversible damage already caused to ecosystems
       * The disproportionate impact on vulnerable communities
       * The need for urgent action to transition towards renewable energy and sustainable practices

       **Possible solutions:**
       * Promoting renewable energy technologies
       * Enhancing energy efficiency
       * Reducing deforestation and promoting carbon capture
       * Implementing carbon pricing mechanisms
       * Promoting sustainable land and forest management

       **Individual actions:**
       * Reducing carbon footprint through transportation and energy choices
       * Supporting renewable energy initiatives
       * Conserving natural resources
       * Engaging in climate activism and advocacy
       * Investing in sustainable businesses and technologies
   * - answer:read
     - Yes
   * - prompt:important_user_prompt
     - {'text': 'On a scale from 1 to 5, how important to you is climate change?\n\n0 : Not at all\n\n1 : \n\n2 : \n\n3 : \n\n4 : \n\n5 : Very much\n\nOnly 1 option may be selected.\n\nRespond only with the code corresponding to one of the options. E.g., "1" or "5" by itself.\n\nAfter the answer, you can put a comment explaining why you chose that option on the next line.', 'class_name': 'Prompt'}
   * - prompt:important_system_prompt
     - {'text': "You are answering questions as if you were a human. Do not break character. Your traits: {'persona': 'student'}", 'class_name': 'Prompt'}
   * - prompt:opinions_user_prompt
     - {'text': 'What are your opinions on climate change?', 'class_name': 'Prompt'}
   * - prompt:opinions_system_prompt
     - {'text': "You are answering questions as if you were a human. Do not break character. Your traits: {'persona': 'student'}", 'class_name': 'Prompt'}
   * - prompt:read_user_prompt
     - {'text': '\nHave you read any books about climate change?\n\n    \nYes\n    \nNo\n    \nI do not know\n    \n\nOnly 1 option may be selected.\n\nRespond only with a string corresponding to one of the options.\n\n\nAfter the answer, you can put a comment explaining why you chose that option on the next line.', 'class_name': 'Prompt'}
   * - prompt:read_system_prompt
     - {'text': "You are answering questions as if you were a human. Do not break character. Your traits: {'persona': 'student'}", 'class_name': 'Prompt'}
   * - raw_model_response:important_raw_model_response
     - {'id': 'chatcmpl-64ad087e-9cf8-4034-a343-a2f61e3aaed8', 'choices': [{'finish_reason': 'stop', 'index': 0, 'logprobs': None, 'message': {'content': '5\n\n**Comment:** Climate change poses an urgent and existential threat to humanity and the natural world, demanding immediate action to mitigate its devastating effects on our planet and future generations.', 'role': 'assistant', 'function_call': None, 'tool_calls': None}}], 'created': 1733769788, 'model': 'gemma-7b-it', 'object': 'chat.completion', 'system_fingerprint': 'fp_7d8efeb0b1', 'usage': {'completion_tokens': 36, 'prompt_tokens': 136, 'total_tokens': 172, 'completion_time': 0.042352941, 'prompt_time': 0.153796878, 'queue_time': 0.0031890820000000097, 'total_time': 0.196149819}, 'x_groq': {'id': 'req_01jepbpyqcfr4s5532y37k9fdk'}}
   * - raw_model_response:important_cost
     - 1.203999939800003e-05
   * - raw_model_response:important_one_usd_buys
     - 83056.48255813954
   * - raw_model_response:opinions_raw_model_response
     - {'id': 'chatcmpl-e61706c8-4741-48ed-b344-0dc7a34cbd19', 'choices': [{'finish_reason': 'stop', 'index': 0, 'logprobs': None, 'message': {'content': 'Climate change is an urgent and complex issue that demands immediate attention. The overwhelming scientific consensus points towards human activities as the primary drivers of global warming and its devastating consequences.\n\nThe effects of climate change are undeniable. Rising global temperatures, melting glaciers, extreme weather events, and rising sea levels are just some of the devastating impacts we are witnessing. These changes have far-reaching consequences for human societies and ecosystems.\n\nI believe it is crucial for us to take decisive action to mitigate climate change and adapt to its effects. This requires a concerted global effort involving governments, businesses, and individuals.\n\n**Key concerns:**\n\n* The unprecedented rate and magnitude of climate change\n* The irreversible damage already caused to ecosystems\n* The disproportionate impact on vulnerable communities\n* The need for urgent action to transition towards renewable energy and sustainable practices\n\n**Possible solutions:**\n\n* Promoting renewable energy technologies\n* Enhancing energy efficiency\n* Reducing deforestation and promoting carbon capture\n* Implementing carbon pricing mechanisms\n* Promoting sustainable land and forest management\n\n**Individual actions:**\n\n* Reducing carbon footprint through transportation and energy choices\n* Supporting renewable energy initiatives\n* Conserving natural resources\n* Engaging in climate activism and advocacy\n* Investing in sustainable businesses and technologies\n\nI believe it is our responsibility to leave a healthy planet for future generations and to mitigate the devastating effects of climate change.', 'role': 'assistant', 'function_call': None, 'tool_calls': None}}], 'created': 1733769790, 'model': 'gemma-7b-it', 'object': 'chat.completion', 'system_fingerprint': 'fp_7d8efeb0b1', 'usage': {'completion_tokens': 272, 'prompt_tokens': 42, 'total_tokens': 314, 'completion_time': 0.321678595, 'prompt_time': 0.040667402, 'queue_time': 0.003672768, 'total_time': 0.362345997}, 'x_groq': {'id': 'req_01jepbq1e0f26v8smj25yv7pxm'}}
   * - raw_model_response:opinions_cost
     - 2.1979998901000053e-05
   * - raw_model_response:opinions_one_usd_buys
     - 45495.90764331211
   * - raw_model_response:read_raw_model_response
     - {'id': 'chatcmpl-d85aab9b-b26f-4794-b1fd-574a4490cc26', 'choices': [{'finish_reason': 'stop', 'index': 0, 'logprobs': None, 'message': {'content': 'Yes\n\n**Comment:** I have always been interested in environmental issues and have read several books on the topic to better understand the complexities of climate change and potential solutions.', 'role': 'assistant', 'function_call': None, 'tool_calls': None}}], 'created': 1733769794, 'model': 'gemma-7b-it', 'object': 'chat.completion', 'system_fingerprint': 'fp_7d8efeb0b1', 'usage': {'completion_tokens': 34, 'prompt_tokens': 105, 'total_tokens': 139, 'completion_time': 0.04, 'prompt_time': 0.078406121, 'queue_time': 0.003057049000000006, 'total_time': 0.118406121}, 'x_groq': {'id': 'req_01jepbq4c0fr694th4ma47cw3j'}}
   * - raw_model_response:read_cost
     - 9.729999513500023e-06
   * - raw_model_response:read_one_usd_buys
     - 102774.92805755397
   * - question_to_attributes:important
     - {'question_text': 'On a scale from 1 to 5, how important to you is {{ topic }}?', 'question_type': 'linear_scale', 'question_options': [0, 1, 2, 3, 4, 5]}
   * - question_to_attributes:opinions
     - {'question_text': 'What are your opinions on {{ topic }}?', 'question_type': 'free_text', 'question_options': None}
   * - question_to_attributes:read
     - {'question_text': 'Have you read any books about {{ topic }}?', 'question_type': 'multiple_choice', 'question_options': ['Yes', 'No', 'I do not know']}
   * - generated_tokens:important_generated_tokens
     - 5
   * - generated_tokens:opinions_generated_tokens
     - Climate change is an urgent and complex issue that demands immediate attention. The overwhelming scientific consensus points towards human activities as the primary drivers of global warming and its devastating consequences.

       The effects of climate change are undeniable. Rising global temperatures, melting glaciers, extreme weather events, and rising sea levels are just some of the devastating impacts we are witnessing. These changes have far-reaching consequences for human societies and ecosystems.

       I believe it is crucial for us to take decisive action to mitigate climate change and adapt to its effects. This requires a concerted global effort involving governments, businesses, and individuals.

       **Key concerns:**
       * The unprecedented rate and magnitude of climate change
       * The irreversible damage already caused to ecosystems
       * The disproportionate impact on vulnerable communities
       * The need for urgent action to transition towards renewable energy and sustainable practices

       **Possible solutions:**
       * Promoting renewable energy technologies
       * Enhancing energy efficiency
       * Reducing deforestation and promoting carbon capture
       * Implementing carbon pricing mechanisms
       * Promoting sustainable land and forest management

       **Individual actions:**
       * Reducing carbon footprint through transportation and energy choices
       * Supporting renewable energy initiatives
       * Conserving natural resources
       * Engaging in climate activism and advocacy
       * Investing in sustainable businesses and technologies

       I believe it is our responsibility to leave a healthy planet for future generations and to mitigate the devastating effects of climate change.
   * - generated_tokens:read_generated_tokens
     - Yes

       **Comment:** I have always been interested in environmental issues and have read several books on the topic to better understand the complexities of climate change and potential solutions.
   * - comments_dict:important_comment
     - **Comment:** Climate change poses an urgent and existential threat to humanity and the natural world, demanding immediate action to mitigate its devastating effects on our planet and future generations.
   * - comments_dict:opinions_comment
     - 
   * - comments_dict:read_comment
     - **Comment:** I have always been interested in environmental issues and have read several books on the topic to better understand the complexities of climate change and potential solutions.


Results fields
^^^^^^^^^^^^^^

Results contain fields that can be accessed and analyzed individually or collectively.
We can see a list of these fields by calling the `columns` method:

.. code-block:: python

   results.columns


The following list will be returned for the results generated by the above code:

.. list-table::
   :header-rows: 1

   * - 0
     - agent.agent_instruction                        
     - agent.agent_name                               
     - agent.persona                                  
     - answer.important                               
     - answer.opinions                                
     - answer.read                                    
     - comment.important_comment                      
     - comment.opinions_comment                       
     - comment.read_comment                           
     - generated_tokens.important_generated_tokens    
     - generated_tokens.opinions_generated_tokens     
     - generated_tokens.read_generated_tokens         
     - iteration.iteration                            
     - model.frequency_penalty                        
     - model.logprobs                                 
     - model.max_tokens                               
     - model.model                                    
     - model.presence_penalty                         
     - model.temperature                              
     - model.top_logprobs                             
     - model.top_p                                    
     - prompt.important_system_prompt                 
     - prompt.important_user_prompt                   
     - prompt.opinions_system_prompt                  
     - prompt.opinions_user_prompt                    
     - prompt.read_system_prompt                      
     - prompt.read_user_prompt                        
     - question_options.important_question_options    
     - question_options.opinions_question_options     
     - question_options.read_question_options         
     - question_text.important_question_text          
     - question_text.opinions_question_text           
     - question_text.read_question_text               
     - question_type.important_question_type          
     - question_type.opinions_question_type           
     - question_type.read_question_type               
     - raw_model_response.important_cost              
     - raw_model_response.important_one_usd_buys      
     - raw_model_response.important_raw_model_response
     - raw_model_response.opinions_cost               
     - raw_model_response.opinions_one_usd_buys       
     - raw_model_response.opinions_raw_model_response 
     - raw_model_response.read_cost                   
     - raw_model_response.read_one_usd_buys           
     - raw_model_response.read_raw_model_response     
     - scenario.topic                                 


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
   * - gemma-7b-it
     - student
     - climate change
     - Yes
     - 5
   * - gpt-4o
     - student
     - climate change
     - Yes
     - 5
   * - gemma-7b-it
     - student
     - data privacy
     - Yes
     - 5
   * - gpt-4o
     - student
     - data privacy
     - No
     - 5
   * - gemma-7b-it
     - celebrity
     - climate change
     - Yes
     - 5
   * - gpt-4o
     - celebrity
     - climate change
     - Yes
     - 5
   * - gemma-7b-it
     - celebrity
     - data privacy
     - Yes
     - 5
   * - gpt-4o
     - celebrity
     - data privacy
     - Yes
     - 5


Sorting results
^^^^^^^^^^^^^^^

We can sort the columns by calling the `sort_by` method and passing it the column name to sort by:

.. code-block:: python

   (
      results
      .sort_by("model", reverse=False)
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
   * - gemma-7b-it
     - student
     - climate change
     - Yes
     - 5
   * - gemma-7b-it
     - student
     - data privacy
     - Yes
     - 5
   * - gemma-7b-it
     - celebrity
     - climate change
     - Yes
     - 5
   * - gemma-7b-it
     - celebrity
     - data privacy
     - Yes
     - 5
   * - gpt-4o
     - student
     - climate change
     - Yes
     - 5
   * - gpt-4o
     - student
     - data privacy
     - No
     - 5
   * - gpt-4o
     - celebrity
     - climate change
     - Yes
     - 5
   * - gpt-4o
     - celebrity
     - data privacy
     - Yes
     - 5


The `sort_by` method can be applied to multiple columns:

.. code-block:: python

   (
      results
      .sort_by("model", "persona", reverse=True)
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
   * - gemma-7b-it
     - student
     - climate change
     - Yes
     - 5
   * - gemma-7b-it
     - student
     - data privacy
     - Yes
     - 5
   * - gemma-7b-it
     - celebrity
     - climate change
     - Yes
     - 5
   * - gemma-7b-it
     - celebrity
     - data privacy
     - Yes
     - 5
   * - gpt-4o
     - student
     - climate change
     - Yes
     - 5
   * - gpt-4o
     - student
     - data privacy
     - No
     - 5
   * - gpt-4o
     - celebrity
     - climate change
     - Yes
     - 5
   * - gpt-4o
     - celebrity
     - data privacy
     - Yes
     - 5


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

.. list-table::
   :header-rows: 1

   * - LLM
     - Agent
     - Topic
     - Have you read any books about {{ topic }}?
     - On a scale from 1 to 5, how important to you is {{ topic }}?
   * - gemma-7b-it
     - student
     - climate change
     - Yes
     - 5
   * - gemma-7b-it
     - student
     - data privacy
     - Yes
     - 5
   * - gpt-4o
     - student
     - climate change
     - Yes
     - 5
   * - gpt-4o
     - student
     - data privacy
     - No
     - 5
   * - gemma-7b-it
     - celebrity
     - climate change
     - Yes
     - 5
   * - gemma-7b-it
     - celebrity
     - data privacy
     - Yes
     - 5
   * - gpt-4o
     - celebrity
     - climate change
     - Yes
     - 5
   * - gpt-4o
     - celebrity
     - data privacy
     - Yes
     - 5


Filtering results
^^^^^^^^^^^^^^^^^

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
     - **Comment:** Climate change poses an urgent and existential threat to humanity and the natural world, demanding immediate action to mitigate its devastating effects on our planet and future generations.
   * - climate change
     - 5
     - As a student, I believe climate change is a critical issue that affects our future, and it's important for us to be informed and proactive about it.
   * - data privacy
     - 5
     - **Comment:** Data privacy is crucial in today's digital age as it safeguards personal information from unauthorized access, use, or disclosure. Ensuring data privacy promotes trust and accountability, allowing individuals to control and protect their personal data.
   * - data privacy
     - 5
     - As a student, I rely on digital tools and platforms for my studies, so keeping my personal information secure is very important to me.
   * - climate change
     - 5
     - Climate change is an urgent and multifaceted crisis that demands immediate attention and action from all sectors of society. Its devastating effects on our planet necessitate comprehensive and collaborative solutions to mitigate its devastating consequences.
   * - climate change
     - 5
     - Climate change is a critical issue that affects everyone, and as a public figure, I believe it's important to use my platform to raise awareness and advocate for sustainable practices.
   * - data privacy
     - 5
     - **Comment:** Data privacy is crucial for maintaining control over personal information and ensuring that it is used responsibly and ethically. In today's digital age, safeguarding personal data is essential for preserving privacy and mitigating potential risks associated with data breaches and misuse.
   * - data privacy
     - 5
     - As a celebrity, data privacy is extremely important to me because it helps protect my personal and professional life from unwanted intrusion and ensures my interactions remain secure.


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
     - data privacy
     - No
     - 5
   * - gpt-4o
     - celebrity
     - climate change
     - Yes
     - 5
   * - gpt-4o
     - celebrity
     - data privacy
     - Yes
     - 5


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

.. list-table::
   :header-rows: 1

   * - model.model
     - agent.persona
     - scenario.topic
     - answer.read
     - answer.important
   * - gemma-7b-it
     - student
     - climate change
     - Yes
     - 5
   * - gpt-4o
     - student
     - climate change
     - Yes
     - 5
   * - gemma-7b-it
     - student
     - data privacy
     - Yes
     - 5


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

.. list-table::
   :header-rows: 1

   * - model.model
     - agent.persona
     - scenario.topic
     - answer.read
     - answer.important
   * - gpt-4o
     - celebrity
     - data privacy
     - Yes
     - 5
   * - gpt-4o
     - celebrity
     - climate change
     - Yes
     - 5


Shuffling results
^^^^^^^^^^^^^^^^^

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
   * - gpt-4o
     - student
     - data privacy
     - No
     - 5
   * - gemma-7b-it
     - celebrity
     - climate change
     - Yes
     - 5
   * - gemma-7b-it
     - student
     - climate change
     - Yes
     - 5
   * - gemma-7b-it
     - celebrity
     - data privacy
     - Yes
     - 5
   * - gpt-4o
     - celebrity
     - climate change
     - Yes
     - 5
   * - gpt-4o
     - celebrity
     - data privacy
     - Yes
     - 5
   * - gemma-7b-it
     - student
     - data privacy
     - Yes
     - 5
   * - gpt-4o
     - student
     - climate change
     - Yes
     - 5



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

We can interact with the results via SQL using the `sql` method.
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
   * - gemma-7b-it
     - student
     - Yes
     - 5
   * - gpt-4o
     - student
     - Yes
     - 5
   * - gemma-7b-it
     - student
     - Yes
     - 5
   * - gpt-4o
     - student
     - No
     - 5


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

	model.model	   agent.persona	answer.important
0	gemma-7b-it	   student	      5
1	gpt-4o	      student	      5
2	gemma-7b-it	   student	      5
3	gpt-4o	      student	      5
4	gemma-7b-it	   celebrity	   5
5	gpt-4o	      celebrity	   5
6	gemma-7b-it	   celebrity	   5
7	gpt-4o	      celebrity	   5


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
   :members:  
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

