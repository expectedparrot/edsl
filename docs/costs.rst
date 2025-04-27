.. _costs:

Estimating & Tracking Costs
===========================

EDSL comes with built-in methods for estimating costs before running your survey jobs, and tracking actual costs after running them. 
This is useful for budgeting and understanding the costs of running surveys with different models and inference services, and determining which models are most efficient for your research goals.

.. note::
    When running jobs remotely, your prompts and responses are cached automatically and can be retrieved again later at no cost.
    Learn more about remote inference caching in the :ref:`remote-caching` section of the docs.


Estimating costs
-----------------

When you create a survey, you can estimate the cost of running it before actually running it. 
This is done by combining the survey with one or more models to create a `Job` object. 
The `Job` object contains all the information needed to run the survey, including the models and inference services used.

There are 2 methods of estimating costs (in USD and credits):

* Call the `estimate_job_cost()` method on a `Job` object (a survey combined with one or more models). This will return the total estimated cost in USD, the estimated input and output tokens, and estimated costs and tokens for each inference service and model used. 

* Call the `remote_inference_cost()` method on a `Coop` client object and pass it the job. This will return the estimated cost in credits and USD. (Credits are required to run surveys remotely. Learn more about using credits in the [Credits](https://docs.expectedparrot.com/en/latest/credits.html) section of the docs.)

For example:

.. code-block:: python 

    from edsl import QuestionMultipleChoice, Survey, Model, ModelList

    q = QuestionMultipleChoice(
        question_name = "color",
        question_text = "Which is your favorite primary color?",
        question_options = ["red", "blue", "yellow"]
    )
    survey = Survey(questions = [q])
    models = ModelList([
        Model("gpt-4o", service_name = "openai"),
        Model("gemini-1.5-flash", service_name = "google")
    ])

    job = survey.by(models)

    job.estimate_job_cost()


This will return:

.. code-block:: python

    {'estimated_total_cost_usd': 0.000697825,
    'total_credits_hold': 0.09999999999999999,
    'estimated_total_input_tokens': 134,
    'estimated_total_output_tokens': 102,
    'detailed_costs': [{'inference_service': 'openai',
    'model': 'gpt-4o',
    'token_type': 'input',
    'price_per_million_tokens': 2.5,
    'tokens': 67,
    'cost_usd': 0.0001675,
    'credits_hold': 0.02},
    {'inference_service': 'openai',
    'model': 'gpt-4o',
    'token_type': 'output',
    'price_per_million_tokens': 10.0,
    'tokens': 51,
    'cost_usd': 0.00051,
    'credits_hold': 0.06},
    {'inference_service': 'google',
    'model': 'gemini-1.5-flash',
    'token_type': 'input',
    'price_per_million_tokens': 0.075,
    'tokens': 67,
    'cost_usd': 5.025e-06,
    'credits_hold': 0.01},
    {'inference_service': 'google',
    'model': 'gemini-1.5-flash',
    'token_type': 'output',
    'price_per_million_tokens': 0.3,
    'tokens': 51,
    'cost_usd': 1.53e-05,
    'credits_hold': 0.01}]}


Using the Coop client object instead:

.. code-block:: python

    from edsl import Coop

    coop = Coop()
    coop.remote_inference_cost(job)


This will return:

.. code-block:: python 

    {'credits_hold': 0.1, 'usd': 0.001}


Calculations
------------

The above-mentioned methods use the following calculation for each question in a survey to estimate the total cost of the job:

1. Estimate the input tokens.
    * Compute the number of characters in the `user_prompt` and `system_prompt`, with any `Agent` and `Scenario` data piped in. (*Note:* Previous answers cannot be piped in because they are not available until the survey is run; they are left as Jinja-bracketed variables in the prompts for purposes of estimating tokens and costs.)
    * Apply a piping multiplier of 2 to the number of characters in the user prompt if it has an answer piped in from a previous question (i.e., if the question has Jinja braces). Otherwise, apply a multiplier of 1.
    * Convert the number of characters into the number of input tokens using a conversion factor of 4 characters per token, rounding down to the nearest whole number. (This approximation was [established by OpenAI](https://help.openai.com/en/articles/4936856-what-are-tokens-and-how-to-count-them).)
2. Estimate the output tokens.
    * Apply a multiplier of 0.75 to the number of input tokens, rounding up to the nearest whole number.
3. Apply the token rates for the model and inference service.
    * Find the model and inference service for the question in the [Pricing](https://www.expectedparrot.com/getting-started/coop-pricing) page:
        *Total cost = (input tokens * input token rate) + (output tokens * output token rate)*
    * If the model is not found, a default price for the inference service provider is used. If both the model and the inference service provider are not found, the following fallback token rates are applied (you will also see a warning message that a model price was not found):
        * USD 1.00 per 1M input tokens
        * USD 1.00 per 1M ouput tokens

4. Convert the total cost in USD to credits.
    * Total cost in credits = total cost in USD * 100, rounded up to the nearest 1/100th credit.

Then sum the costs for all question prompts to get the total cost of the job.
A notebook example is available [here](https://www.expectedparrot.com/content/RobinHorton/estimating-job-costs-notebook).


Tracking costs
--------------

After running a survey job, you can track the actual token costs incurred for each question in the `raw_model_response` columns of the `Results` that are generated for your survey:

* **raw_model_response.<question_name>_cost**: The cost of the result for the relevant question, applying the token quanities & prices.
* **raw_model_response.<question_name>_input_price_per_million_tokenss**: The price per million input tokens for the relevant question for the relevant model.
* **raw_model_response.<question_name>_input_tokens**: The number of input tokens for the relevant question for the relevant model.
* **raw_model_response.<question_name>_one_usd_buys**: The number of identical results for the relevant question that 1USD would cover. 
* **raw_model_response.<question_name>_output_price_per_million_tokens**: The price per million output tokens for the relevant question for the relevant model.
* **raw_model_response.<question_name>_output_tokens**: The number of output tokens for the relevant question for the relevant model.
* **raw_model_response.<question_name>_raw_model_response**: The raw model response for the relevant question.

Details can also be viewed at the [Jobs](https://www.expectedparrot.com/home/remote-inference) and [Transactions](https://www.expectedparrot.com/home/transactions) pages of your Coop account.

For example, here we inspect the costs of running the job from above:

.. code-block:: python

    results = job.run()

    results.select("raw_model_response.*")


Output:

.. list-table::
  :header-rows: 1

  * - model.model
    - question_text.read_question_text
    - question_text.important_question_text
    - raw_model_response.read_input_price_per_million_tokens
    - raw_model_response.important_output_tokens
    - raw_model_response.important_output_price_per_million_tokens
    - raw_model_response.read_one_usd_buys
    - raw_model_response.important_raw_model_response
    - raw_model_response.important_input_price_per_million_tokens
    - raw_model_response.read_input_tokens
    - raw_model_response.read_raw_model_response
    - raw_model_response.important_one_usd_buys
    - raw_model_response.read_output_price_per_million_tokens
    - raw_model_response.read_cost
    - raw_model_response.read_output_tokens
    - raw_model_response.important_input_tokens
    - raw_model_response.important_cost
  * - gemini-1.5-flash
    - Have you read any books about {{ scenario.topic }}?
    - On a scale from 1 to 5, how important to you is {{ scenario.topic }}?
    - 0.075000
    - 53
    - 0.300000
    - 42872.461058
    - {'candidates': [{'content': {'parts': [{'text': "5\n\nIt's, like, a huge deal!  The future of the planet is at stake, and that affects everything –  from the environment to the economy to, you know, my future.  It's definitely something I worry about.\n"}], 'role': 'model'}, 'finish_reason': 1, 'safety_ratings': [{'category': 8, 'probability': 1, 'blocked': False}, {'category': 10, 'probability': 1, 'blocked': False}, {'category': 7, 'probability': 1, 'blocked': False}, {'category': 9, 'probability': 1, 'blocked': False}], 'avg_logprobs': -0.2145003372768186, 'token_count': 0, 'grounding_attributions': []}], 'usage_metadata': {'prompt_token_count': 128, 'candidates_token_count': 53, 'total_token_count': 181, 'cached_content_token_count': 0}, 'model_version': 'gemini-1.5-flash'}
    - 0.075000
    - 95
    - {'candidates': [{'content': {'parts': [{'text': "Yes\n\nI've read a few articles and some chapters from textbooks for my environmental science classes, which covered climate change extensively.  It's not quite the same as reading a whole book dedicated to the topic, but I've definitely learned about it.\n"}], 'role': 'model'}, 'finish_reason': 1, 'safety_ratings': [{'category': 8, 'probability': 1, 'blocked': False}, {'category': 10, 'probability': 1, 'blocked': False}, {'category': 7, 'probability': 1, 'blocked': False}, {'category': 9, 'probability': 1, 'blocked': False}], 'avg_logprobs': -0.15844399840743453, 'token_count': 0, 'grounding_attributions': []}], 'usage_metadata': {'prompt_token_count': 95, 'candidates_token_count': 54, 'total_token_count': 149, 'cached_content_token_count': 0}, 'model_version': 'gemini-1.5-flash'}
    - 39215.691903
    - 0.300000
    - 0.000023
    - 54
    - 128
    - 0.000025
  * - gpt-4o
    - Have you read any books about {{ scenario.topic }}?
    - On a scale from 1 to 5, how important to you is {{ scenario.topic }}?
    - 2.500000
    - 32
    - 10.000000
    - 1724.137931
    - {'id': 'chatcmpl-BQaCQLYP5PB3vEeEOElownyIV7jLX', 'choices': [{'finish_reason': 'stop', 'index': 0, 'logprobs': None, 'message': {'content': "5  \nClimate change is a critical issue that affects the entire planet and future generations, so I believe it's very important to address and find solutions for it.", 'refusal': None, 'role': 'assistant', 'audio': None, 'function_call': None, 'tool_calls': None, 'annotations': []}}], 'created': 1745675378, 'model': 'gpt-4o-2024-08-06', 'object': 'chat.completion', 'service_tier': 'default', 'system_fingerprint': 'fp_f5bdcc3276', 'usage': {'completion_tokens': 32, 'prompt_tokens': 131, 'total_tokens': 163, 'completion_tokens_details': {'accepted_prediction_tokens': 0, 'audio_tokens': 0, 'reasoning_tokens': 0, 'rejected_prediction_tokens': 0}, 'prompt_tokens_details': {'audio_tokens': 0, 'cached_tokens': 0}}}
    - 2.500000
    - 96
    - {'id': 'chatcmpl-BQaCTYk259rsV3vcpoA2vi6XP7yhd', 'choices': [{'finish_reason': 'stop', 'index': 0, 'logprobs': None, 'message': {'content': "Yes  \nI've read a few books on climate change as part of my studies to better understand the environmental challenges we face and what actions can be taken to mitigate them.", 'refusal': None, 'role': 'assistant', 'audio': None, 'function_call': None, 'tool_calls': None, 'annotations': []}}], 'created': 1745675381, 'model': 'gpt-4o-2024-08-06', 'object': 'chat.completion', 'service_tier': 'default', 'system_fingerprint': 'fp_f5bdcc3276', 'usage': {'completion_tokens': 34, 'prompt_tokens': 96, 'total_tokens': 130, 'completion_tokens_details': {'accepted_prediction_tokens': 0, 'audio_tokens': 0, 'reasoning_tokens': 0, 'rejected_prediction_tokens': 0}, 'prompt_tokens_details': {'audio_tokens': 0, 'cached_tokens': 0}}}
    - 1544.401544
    - 10.000000
    - 0.000580
    - 34
    - 131
    - 0.000647
  * - gemini-1.5-flash
    - Have you read any books about {{ scenario.topic }}?
    - On a scale from 1 to 5, how important to you is {{ scenario.topic }}?
    - 0.075000
    - 48
    - 0.300000
    - 52287.589235
    - {'candidates': [{'content': {'parts': [{'text': "1\n\nHouse prices are something I think about, but it's not something that's keeping me up at night.  It's more of a long-term consideration than something I'm actively focused on right now.\n"}], 'role': 'model'}, 'finish_reason': 1, 'safety_ratings': [{'category': 8, 'probability': 1, 'blocked': False}, {'category': 10, 'probability': 1, 'blocked': False}, {'category': 7, 'probability': 1, 'blocked': False}, {'category': 9, 'probability': 1, 'blocked': False}], 'avg_logprobs': -0.22673827409744263, 'token_count': 0, 'grounding_attributions': []}], 'usage_metadata': {'prompt_token_count': 128, 'candidates_token_count': 48, 'total_token_count': 176, 'cached_content_token_count': 0}, 'model_version': 'gemini-1.5-flash'}
    - 0.075000
    - 95
    - {'candidates': [{'content': {'parts': [{'text': "No\n\nI'm a student, so I haven't had much time to read books outside of my coursework.  House prices aren't really something I've focused on yet.\n"}], 'role': 'model'}, 'finish_reason': 1, 'safety_ratings': [{'category': 8, 'probability': 1, 'blocked': False}, {'category': 10, 'probability': 1, 'blocked': False}, {'category': 7, 'probability': 1, 'blocked': False}, {'category': 9, 'probability': 1, 'blocked': False}], 'avg_logprobs': -0.12296264171600342, 'token_count': 0, 'grounding_attributions': []}], 'usage_metadata': {'prompt_token_count': 95, 'candidates_token_count': 40, 'total_token_count': 135, 'cached_content_token_count': 0}, 'model_version': 'gemini-1.5-flash'}
    - 41666.672500
    - 0.300000
    - 0.000019
    - 40
    - 128
    - 0.000024
  * - gpt-4o
    - Have you read any books about {{ scenario.topic }}?
    - On a scale from 1 to 5, how important to you is {{ scenario.topic }}?
    - 2.500000
    - 32
    - 10.000000
    - 2127.659574
    - {'id': 'chatcmpl-BQaCUaNZYyLh3T6gtpHnV8YinocJv', 'choices': [{'finish_reason': 'stop', 'index': 0, 'logprobs': None, 'message': {'content': "3  \nAs a student, I'm not in the market to buy a house right now, but I am interested in understanding the housing market for future planning.", 'refusal': None, 'role': 'assistant', 'audio': None, 'function_call': None, 'tool_calls': None, 'annotations': []}}], 'created': 1745675382, 'model': 'gpt-4o-2024-08-06', 'object': 'chat.completion', 'service_tier': 'default', 'system_fingerprint': 'fp_f5bdcc3276', 'usage': {'completion_tokens': 32, 'prompt_tokens': 131, 'total_tokens': 163, 'completion_tokens_details': {'accepted_prediction_tokens': 0, 'audio_tokens': 0, 'reasoning_tokens': 0, 'rejected_prediction_tokens': 0}, 'prompt_tokens_details': {'audio_tokens': 0, 'cached_tokens': 0}}}
    - 2.500000
    - 96
    - {'id': 'chatcmpl-BQaCSxNYx8KL3iJGbA3ARSAoUaxAC', 'choices': [{'finish_reason': 'stop', 'index': 0, 'logprobs': None, 'message': {'content': "No  \nI haven't read any books specifically about house prices, but I've come across articles and discussions about them.", 'refusal': None, 'role': 'assistant', 'audio': None, 'function_call': None, 'tool_calls': None, 'annotations': []}}], 'created': 1745675380, 'model': 'gpt-4o-2024-08-06', 'object': 'chat.completion', 'service_tier': 'default', 'system_fingerprint': 'fp_f5bdcc3276', 'usage': {'completion_tokens': 23, 'prompt_tokens': 96, 'total_tokens': 119, 'completion_tokens_details': {'accepted_prediction_tokens': 0, 'audio_tokens': 0, 'reasoning_tokens': 0, 'rejected_prediction_tokens': 0}, 'prompt_tokens_details': {'audio_tokens': 0, 'cached_tokens': 0}}}
    - 1544.401544
    - 10.000000
    - 0.000470
    - 23
    - 131
    - 0.000647
  * - gemini-1.5-flash
    - Have you read any books about {{ scenario.topic }}?
    - On a scale from 1 to 5, how important to you is {{ scenario.topic }}?
    - 0.075000
    - 55
    - 0.300000
    - 29304.034247
    - {'candidates': [{'content': {'parts': [{'text': "5\n\nIt's absolutely crucial.  As someone with a global platform, I see firsthand the devastating effects of climate change – from extreme weather events impacting communities to the threats to biodiversity.  We need urgent action, and I'm committed to doing my part.\n"}], 'role': 'model'}, 'finish_reason': 1, 'safety_ratings': [{'category': 8, 'probability': 1, 'blocked': False}, {'category': 10, 'probability': 1, 'blocked': False}, {'category': 7, 'probability': 1, 'blocked': False}, {'category': 9, 'probability': 1, 'blocked': False}], 'avg_logprobs': -0.25197906494140626, 'token_count': 0, 'grounding_attributions': []}], 'usage_metadata': {'prompt_token_count': 128, 'candidates_token_count': 55, 'total_token_count': 183, 'cached_content_token_count': 0}, 'model_version': 'gemini-1.5-flash'}
    - 0.075000
    - 95
    - {'candidates': [{'content': {'parts': [{'text': "Yes\n\nOh honey,  I've read *so many* books about climate change.  It's a topic I'm incredibly passionate about, and I try to stay informed.  Between interviews and red carpets, I always have a stack of books on my nightstand, and lately, a lot of them have been focused on environmental issues.  It's crucial to be aware of what's happening to our planet.\n"}], 'role': 'model'}, 'finish_reason': 1, 'safety_ratings': [{'category': 8, 'probability': 1, 'blocked': False}, {'category': 10, 'probability': 1, 'blocked': False}, {'category': 7, 'probability': 1, 'blocked': False}, {'category': 9, 'probability': 1, 'blocked': False}], 'avg_logprobs': -0.29773031870524086, 'token_count': 0, 'grounding_attributions': []}], 'usage_metadata': {'prompt_token_count': 95, 'candidates_token_count': 90, 'total_token_count': 185, 'cached_content_token_count': 0}, 'model_version': 'gemini-1.5-flash'}
    - 38314.181794
    - 0.300000
    - 0.000034
    - 90
    - 128
    - 0.000026
  * - gpt-4o
    - Have you read any books about {{ scenario.topic }}?
    - On a scale from 1 to 5, how important to you is {{ scenario.topic }}?
    - 2.500000
    - 39
    - 10.000000
    - 1503.759398
    - {'id': 'chatcmpl-BQaCSmgqiBdOgYN7hW2qux0PmZvSe', 'choices': [{'finish_reason': 'stop', 'index': 0, 'logprobs': None, 'message': {'content': "5  \nClimate change is one of the most pressing issues of our time, and as a public figure, I believe it's crucial to use my platform to raise awareness and advocate for meaningful action.", 'refusal': None, 'role': 'assistant', 'audio': None, 'function_call': None, 'tool_calls': None, 'annotations': []}}], 'created': 1745675380, 'model': 'gpt-4o-2024-08-06', 'object': 'chat.completion', 'service_tier': 'default', 'system_fingerprint': 'fp_d8864f8b6b', 'usage': {'completion_tokens': 39, 'prompt_tokens': 133, 'total_tokens': 172, 'completion_tokens_details': {'accepted_prediction_tokens': 0, 'audio_tokens': 0, 'reasoning_tokens': 0, 'rejected_prediction_tokens': 0}, 'prompt_tokens_details': {'audio_tokens': 0, 'cached_tokens': 0}}}
    - 2.500000
    - 98
    - {'id': 'chatcmpl-BQaCQav47AtdUvfbBlWZWtGOzMwXY', 'choices': [{'finish_reason': 'stop', 'index': 0, 'logprobs': None, 'message': {'content': "Yes  \nAs someone in the public eye, I try to stay informed about important issues like climate change, so I've read a few books on the subject to better understand its impact and what can be done.", 'refusal': None, 'role': 'assistant', 'audio': None, 'function_call': None, 'tool_calls': None, 'annotations': []}}], 'created': 1745675378, 'model': 'gpt-4o-2024-08-06', 'object': 'chat.completion', 'service_tier': 'default', 'system_fingerprint': 'fp_d8864f8b6b', 'usage': {'completion_tokens': 42, 'prompt_tokens': 98, 'total_tokens': 140, 'completion_tokens_details': {'accepted_prediction_tokens': 0, 'audio_tokens': 0, 'reasoning_tokens': 0, 'rejected_prediction_tokens': 0}, 'prompt_tokens_details': {'audio_tokens': 0, 'cached_tokens': 0}}}
    - 1384.083045
    - 10.000000
    - 0.000665
    - 42
    - 133
    - 0.000723
  * - gemini-1.5-flash
    - Have you read any books about {{ scenario.topic }}?
    - On a scale from 1 to 5, how important to you is {{ scenario.topic }}?
    - 0.075000
    - 59
    - 0.300000
    - 35180.304746
    - {'candidates': [{'content': {'parts': [{'text': "3\n\nHonestly, it's something I think about, but it's not my biggest concern.  I mean, a nice place to live is great, but my career and family take precedence.  Plus, I have people who handle that kind of thing for me, thankfully!\n"}], 'role': 'model'}, 'finish_reason': 1, 'safety_ratings': [{'category': 8, 'probability': 1, 'blocked': False}, {'category': 10, 'probability': 1, 'blocked': False}, {'category': 7, 'probability': 1, 'blocked': False}, {'category': 9, 'probability': 1, 'blocked': False}], 'avg_logprobs': -0.2841725430246127, 'token_count': 0, 'grounding_attributions': []}], 'usage_metadata': {'prompt_token_count': 128, 'candidates_token_count': 59, 'total_token_count': 187, 'cached_content_token_count': 0}, 'model_version': 'gemini-1.5-flash'}
    - 0.075000
    - 95
    - {'candidates': [{'content': {'parts': [{'text': "Yes\n\nI mean, honestly, who *hasn't* been obsessed with the housing market lately?  It's practically a national pastime at this point!  I've skimmed a few, mostly for research for a role, but let's be real, the real estate market is its own kind of wild, unpredictable drama.\n"}], 'role': 'model'}, 'finish_reason': 1, 'safety_ratings': [{'category': 8, 'probability': 1, 'blocked': False}, {'category': 10, 'probability': 1, 'blocked': False}, {'category': 7, 'probability': 1, 'blocked': False}, {'category': 9, 'probability': 1, 'blocked': False}], 'avg_logprobs': -0.33602206807740975, 'token_count': 0, 'grounding_attributions': []}], 'usage_metadata': {'prompt_token_count': 95, 'candidates_token_count': 71, 'total_token_count': 166, 'cached_content_token_count': 0}, 'model_version': 'gemini-1.5-flash'}
    - 36630.042024
    - 0.300000
    - 0.000028
    - 71
    - 128
    - 0.000027
  * - gpt-4o
    - Have you read any books about {{ scenario.topic }}?
    - On a scale from 1 to 5, how important to you is {{ scenario.topic }}?
    - 2.500000
    - 31
    - 10.000000
    - 1904.761905
    - {'id': 'chatcmpl-BQaCRYMuhgJBDz0LtE0dX5Nil89RL', 'choices': [{'finish_reason': 'stop', 'index': 0, 'logprobs': None, 'message': {'content': "3  \nAs a celebrity, I have an interest in real estate both as an investment and for personal living spaces, but it's not my primary focus.", 'refusal': None, 'role': 'assistant', 'audio': None, 'function_call': None, 'tool_calls': None, 'annotations': []}}], 'created': 1745675379, 'model': 'gpt-4o-2024-08-06', 'object': 'chat.completion', 'service_tier': 'default', 'system_fingerprint': 'fp_d8864f8b6b', 'usage': {'completion_tokens': 31, 'prompt_tokens': 133, 'total_tokens': 164, 'completion_tokens_details': {'accepted_prediction_tokens': 0, 'audio_tokens': 0, 'reasoning_tokens': 0, 'rejected_prediction_tokens': 0}, 'prompt_tokens_details': {'audio_tokens': 0, 'cached_tokens': 0}}}
    - 2.500000
    - 98
    - {'id': 'chatcmpl-BQaCRamWhwJssHEfAOQCBR6UdQlcj', 'choices': [{'finish_reason': 'stop', 'index': 0, 'logprobs': None, 'message': {'content': "No  \nI haven't read any books specifically about house prices, but I've definitely heard a lot about the market through various conversations and media.", 'refusal': None, 'role': 'assistant', 'audio': None, 'function_call': None, 'tool_calls': None, 'annotations': []}}], 'created': 1745675379, 'model': 'gpt-4o-2024-08-06', 'object': 'chat.completion', 'service_tier': 'default', 'system_fingerprint': 'fp_d8864f8b6b', 'usage': {'completion_tokens': 28, 'prompt_tokens': 98, 'total_tokens': 126, 'completion_tokens_details': {'accepted_prediction_tokens': 0, 'audio_tokens': 0, 'reasoning_tokens': 0, 'rejected_prediction_tokens': 0}, 'prompt_tokens_details': {'audio_tokens': 0, 'cached_tokens': 0}}}
    - 1556.420233
    - 10.000000
    - 0.000525
    - 28
    - 133
    - 0.000642


We can see the details at Coop as well.
Your `Jobs page <https://www.expectedparrot.com/home/remote-inference>`_ will show the actual costs of each survey job.

.. image:: static/jobs_cost_details.png
   :alt: Jobs page
   :align: center


.. html::

    <br>


Your `Transactions page <https://www.expectedparrot.com/home/transactions>`_ will show the additional information about credits on hold based on cost estimates together with actual costs of each survey job.

.. image:: static/transactions_cost_details.png
   :alt: Transactions page
   :align: center


.. html::

    <br>


For more on credits, please see the [Credits](https://docs.expectedparrot.com/en/latest/credits.html) section of the docs.