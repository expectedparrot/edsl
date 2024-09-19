.. _token_usage:

Token usage
===========

EDSL comes with a variety of features for monitoring token usage.
These include:

* A method for setting the requests per minute (RPM) and tokens per minute (TPM) for a model that you are using.
* Methods for turning off default prompt features to reduce token usage. 
* Features for calculating next token probabilities.


Token limits 
------------

Token limits refer to the maximum number of tokens that a language model can process in a single input prompt or output generation.
A token limit affects how much text you can send to a model in one go. 
A language model provider should provide information about the token limits for each model that is associated with your account and API key.
When running a big job in EDSL, you may encounter token limits, which can be managed by adjusting the token limits for a model.


RPM: Requests Per Minute
^^^^^^^^^^^^^^^^^^^^^^^^
RPM stands for Requests Per Minute, which measures the number of API requests that a user can make to a language model within a minute. 
This is a metric for managing the load and traffic that a model can handle.


TPM: Tokens Per Minute
^^^^^^^^^^^^^^^^^^^^^^
TPM stands for Tokens Per Minute, which is a metric for tracking the volume of tokens processed by a language model within a minute. 
This metric typically tracks usage for billing purposes. 


Default token limits
--------------------
Here we inspect the default language model and its parameters, including the token limits:

.. code-block:: python

    from edsl import Model

    model = Model() 
    model


This will show the following information:

.. code-block:: python

    {
        "model": "gpt-4o",
        "parameters": {
            "temperature": 0.5,
            "max_tokens": 1000,
            "top_p": 1,
            "frequency_penalty": 0,
            "presence_penalty": 0,
            "logprobs": false,
            "top_logprobs": 3
        }
    }


We can also inspect the RPM and TPM for the model:

.. code-block:: python

    [model.RPM, model.TPM]


This will show the following information:

.. code-block:: python

    [100, 480000.0]



Modifying token limits
----------------------

We can reset the default RPM and TPM and then check the new values.
Note that the new RPM and TPM are automatically offset by 20% of the specified values to ensure that the model does not exceed the token limits:

.. code-block:: python

    model.set_rate_limits(rpm=10, tpm=10)

    [model.RPM, model.TPM]


This will show the following information:

.. code-block:: python

    [8.0, 8.0]


Here we change it again:

.. code-block:: python

    model = Model()

    model.set_rate_limits(rpm=100, tpm=1000)

    [model.RPM, model.TPM]


This will again show the specified values have been reset with a 20% offset:

.. code-block:: python

    [80.0, 800.0]


Please note that the token limits are subject to the constraints of the model and the API key associated with the model.
Let us know if you have any questions or need further assistance with token limits. 


Methods for reducing token usage 
--------------------------------

There are several ways to reduce the tokens required to run a question or survey.


Turning off question commments
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Each question type (other than `free_text`) automatically includes a `comment` field that gives the answering model a place to put additional information about its response to a question.
This serves as an outlet for a chatty model to return context about an answer without violating formatting instructions (e.g., a model may want to provide an explanation for a mutiple choice response but the answer to the question must only be one of the answer options).
Question comments can also be useful when used with survey "memory" rules, giving a model an opportunity to simulate a "chain of thought" across multiple survey questions.
(By default, questions are administered asynchronously; a model does not have context of other questions and answers in a survey unless memory rules are applied.)
Comments can also provide insight into non-responsive (`None`) answers: a model may use the comments field to describe a point of confusion about a question.

Because the question `comment` field requires additional tokens, it can sometimes be cost-effective to exclude the field from question prompts.
This is done by passing a boolean parameter `include_comment = False` when constructing a question. 
For example:

.. code-block:: python

    from edsl import QuestionNumerical, ScenarioList

    q = QuestionNumerical(
        question_name = "sum",
        question_text = "What is the sum of {{ number_1 }} and {{ number_2 }}?",
        include_comment = False
    )

    some_numbers = {
        "number_1": [0,1,2,3,4],
        "number_2": [5,4,3,2,1]
    }

    s = ScenarioList.from_nested_dict(some_numbers)

    results = q.by(s).run()

    results.select("number_1", "number_2", "sum").print(format="rich")


Output:

.. code-block:: text 

    ┏━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━┓
    ┃ scenario  ┃ scenario  ┃ answer ┃
    ┃ .number_1 ┃ .number_2 ┃ .sum   ┃
    ┡━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━┩
    │ 0         │ 5         │ 5      │
    ├───────────┼───────────┼────────┤
    │ 1         │ 4         │ 5      │
    ├───────────┼───────────┼────────┤
    │ 2         │ 3         │ 5      │
    ├───────────┼───────────┼────────┤
    │ 3         │ 2         │ 5      │
    ├───────────┼───────────┼────────┤
    │ 4         │ 1         │ 5      │
    └───────────┴───────────┴────────┘