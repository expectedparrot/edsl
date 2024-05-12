.. _exceptions:

Exceptions
==========

Details on exceptions raised during the execution of a survey can be found in the `Results` object that is returned when a survey is run. 
The `Results` method `show_exceptions()` can be called to display these exceptions in a table.

Here's an example of a poorly written question that is likely to raise an exception:

.. code-block:: python

    from edsl.questions import QuestionMultipleChoice

    q = QuestionMultipleChoice(
        question_name = "bad_instruction",
        question_text = "What is your favorite color?",
        question_options = ["breakfast", "lunch", "dinner"] # Non-sensical options for the question
    )

    results = q.run()


The above code will likely raise a `QuestionAnswerValidationError` exception because the question options are not related to the question text.

This is the initial exception message that will be displayed:

.. code-block:: text

    Exceptions were raised in the following interviews: [0]
    The returned results have a ".show_exceptions()" attribute e.g., 

    >>> results = suvey.by(agents).by(scenarios).run() 
    >>> results.show_exceptions()

    Exceptions details are available here: 

    >>> from edsl import shared_globals
    >>> shared_globals['edsl_runner_exceptions'].show_exceptions()

    For more details see documentation: https://docs.expectedparrot.com/en/latest/exceptions.html


We can then call `results.show_exceptions()` to see the details of the exceptions that were raised:

.. code-block:: python

    results.show_exceptions()


This will display a table showing the question name, the exception that was raised, the time the exception was raised, and the traceback of the exception:

.. code-block:: text

    ┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ Question     ┃                                  ┃                    ┃                      ┃
    ┃ name         ┃ Exception                        ┃               Time ┃ Traceback            ┃
    ┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
    │ bad_instruc… │ QuestionAnswerValidationError('… │  1715454910.892732 │                      │
    │              │ code must be a string, a         │                    │                      │
    │              │ bytes-like object or a real      │                    │                      │
    │              │ number (got This question seems  │                    │                      │
    │              │ to be malformed. Favorite colors │                    │                      │
    │              │ are not typically associated     │                    │                      │
    │              │ with meals. Please provide       │                    │                      │
    │              │ appropriate options for favorite │                    │                      │
    │              │ colors.).')                      │                    │                      │
    │ bad_instruc… │ QuestionAnswerValidationError("… │ 1715454913.7596118 │                      │
    │              │ code must be a string, a         │                    │                      │
    │              │ bytes-like object or a real      │                    │                      │
    │              │ number (got The question is      │                    │                      │
    │              │ about my favorite color, which   │                    │                      │
    │              │ isn't represented by any of the  │                    │                      │
    │              │ options provided as they are     │                    │                      │
    │              │ meals of the day. Please provide │                    │                      │
    │              │ color options for a valid        │                    │                      │
    │              │ selection.).")                   │                    │                      │
    │ bad_instruc… │ QuestionAnswerValidationError('… │   1715454917.53185 │                      │
    │              │ code must be a string, a         │                    │                      │
    │              │ bytes-like object or a real      │                    │                      │
    │              │ number (got Invalid).')          │                    │                      │
    │ bad_instruc… │ QuestionAnswerValidationError('… │  1715454923.154378 │                      │
    │              │ code must be a string, a         │                    │                      │
    │              │ bytes-like object or a real      │                    │                      │
    │              │ number (got The options provided │                    │                      │
    │              │ do not include colors, they are  │                    │                      │
    │              │ meal times. Therefore, I cannot  │                    │                      │
    │              │ select a favorite color from     │                    │                      │
    │              │ these options.).')               │                    │                      │
    │ bad_instruc… │ QuestionAnswerValidationError('… │ 1715454933.1015732 │                      │
    │              │ code must be a string, a         │                    │                      │
    │              │ bytes-like object or a real      │                    │                      │
    │              │ number (got Invalid).')          │                    │                      │
    │ bad_instruc… │ InterviewErrorPriorTaskCanceled… │  1715454933.102806 │                      │
    │              │ tasks failed for                 │                    │                      │
    │              │ bad_instruction')                │                    │                      │
    └──────────────┴──────────────────────────────────┴────────────────────┴──────────────────────┘



.. .. automodule:: edsl.results.Results
..    :members: show_exceptions
..    :undoc-members:
..    :show-inheritance: