.. _token_limits:

Token limits
============
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
        "model": "gpt-4-1106-preview",
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

    [8000.0, 1600000.0]



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
