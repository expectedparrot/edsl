Quickstart tutorial
===================

This page shows some quickstart examples for constructing questions and surveys and administering
them to AI agents.

See our getting started tutorial notebooks for more detailed examples and explanations:

| `Starter Tutorial <https://deepnote.com/workspace/expected-parrot-c2fa2435-01e3-451d-ba12-9c36b3b87ad9/project/Expected-Parrot-examples-b457490b-fc5d-45e1-82a5-a66e1738a4b9/notebook/Tutorial%20-%20Starter%20Tutorial-e080f5883d764931960d3920782baf34>`__
| `Building Your Research <https://deepnote.com/workspace/expected-parrot-c2fa2435-01e3-451d-ba12-9c36b3b87ad9/project/Expected-Parrot-examples-b457490b-fc5d-45e1-82a5-a66e1738a4b9/notebook/Tutorial%20-%20Building%20Your%20Research-444f68e01bb24974a796058f55e670c7>`__
| `Exploring Your Results <https://deepnote.com/workspace/expected-parrot-c2fa2435-01e3-451d-ba12-9c36b3b87ad9/project/Expected-Parrot-examples-b457490b-fc5d-45e1-82a5-a66e1738a4b9/notebook/Tutorial%20-%20Exploring%20Your%20Results-bb273d63fed340efab082accce308219>`__

and a variety of other notebooks exploring use cases and features `here <https://deepnote.com/workspace/expected-parrot-c2fa2435-01e3-451d-ba12-9c36b3b87ad9/project/Expected-Parrot-examples-b457490b-fc5d-45e1-82a5-a66e1738a4b9/notebook/Docs%20-%20Questions-17430978a5634fc4ada3127b6b9bcd66>`__.

Skip to sections of this quickstart tutorial:

| * `Creating questions`_
| * `Parameterizing questions`_
| * `Administering questions & surveys`_
| * `Adding AI agents`_
| * `Specifying LLMs`_

Results for quickstart code can be viewed notebooks:
`Questions <https://deepnote.com/workspace/expected-parrot-c2fa2435-01e3-451d-ba12-9c36b3b87ad9/project/Expected-Parrot-examples-b457490b-fc5d-45e1-82a5-a66e1738a4b9/notebook/Docs%20-%20Questions-17430978a5634fc4ada3127b6b9bcd66>`__
- `Surveys <https://deepnote.com/workspace/expected-parrot-c2fa2435-01e3-451d-ba12-9c36b3b87ad9/project/Expected-Parrot-examples-b457490b-fc5d-45e1-82a5-a66e1738a4b9/notebook/Docs%20-%20Surveys-e6a1c6b358e4473289d97fa377002cd6>`__
- `Agents <https://deepnote.com/workspace/expected-parrot-c2fa2435-01e3-451d-ba12-9c36b3b87ad9/project/Expected-Parrot-examples-b457490b-fc5d-45e1-82a5-a66e1738a4b9/notebook/Docs%20-%20Agents-7b70a3e973754f18b791250db5bd7933>`__
- `Models <https://deepnote.com/workspace/expected-parrot-c2fa2435-01e3-451d-ba12-9c36b3b87ad9/project/Expected-Parrot-examples-b457490b-fc5d-45e1-82a5-a66e1738a4b9/notebook/Docs%20-%20Models-cf5f11d7b5074908a40fda9c81b18f93>`__



.. _creating_questions:
Creating questions
------------------

.. _multiple-choice:
Multiple choice
^^^^^^^^^^^^^^^

This question type prompts the agent to select a single option from a range of options.

.. code-block:: python

    from edsl import QuestionMultipleChoice
    q_mc = QuestionMultipleChoice(
        question_name = "q_mc",
        question_text = "How often do you shop for clothes?",
        question_options = [
            "Rarely or never",
            "Annually",
            "Seasonally",
            "Monthly",
            "Daily"
        ]
    )

.. _checkbox:
Checkbox
^^^^^^^^

This question type prompts the agent to select one or more options from a range of options, which are returned as a list.
You can optionally specify the minimum and maximum number of options that can be selected.

.. code-block:: python

    from edsl import QuestionCheckBox
    q_cb = QuestionCheckBox(
        question_name = "q_cb",
        question_text = "Which of the following factors are important to you in making decisions about clothes shopping? Select all that apply.",
        question_options = [
            "Price",
            "Quality",
            "Brand Reputation",
            "Style and Design",
            "Fit and Comfort",
            "Customer Reviews and Recommendations",
            "Ethical and Sustainable Practices",
            "Return Policy",
            "Convenience",
            "Other"
        ],
        min_selections = 1, # This is optional
        max_selections = 3  # This is optional
    )

.. _linear_scale:
Linear scale
^^^^^^^^^^^^

This question type prompts the agent to select a single option from a range of integer values.

.. code-block:: python

    from edsl.questions import QuestionLinearScale

    q_ls = QuestionLinearScale(
        question_name = "q_ls",
        question_text = "On a scale of 0-10, how much do you typically enjoy clothes shopping? (0 = Not at all, 10 = Very much)",
        question_options = [0,1,2,3,4,5,6,7,8,9,10]
    )

.. _yes-no:
Yes / No
^^^^^^^^^^^^

A yes/no question requires the respondent to respond “yes” or “no”.
Response options are set by default and not modifiable. To include other
options use a multiple choice question.

.. code-block:: python 

    from edsl.questions import QuestionYesNo
    
    q_yn = QuestionYesNo(
        question_name = "q_yn",
        question_text = "Have you ever felt excluded or frustrated by the standard sizes of the fashion industry?", 
    )

.. _budget:
Budget
^^^^^^

This question prompts the agent to distribute a budget across a set of options.

.. code-block:: python

    from edsl.questions import QuestionBudget

    q_bg = QuestionBudget(
        question_name = "q_bg",
        question_text = "Estimate the percentage of your total time spent shopping for clothes in each of the following modes.",
        question_options=[
            "Online",
            "Malls",
            "Freestanding stores",
            "Mail order catalogs",
            "Other"
        ],
        budget_sum = 100,
    )

.. _freetext:
Free text 
^^^^^^^^^

This question type prompts the agent to format the response as unstructured text.

.. code-block:: python

    from edsl.questions import QuestionFreeText

    q_ft = QuestionFreeText(
        question_name = "q_ft",
        question_text = "What improvements would you like to see in clothing options for tall women?",
        allow_nonresponse = False,
    )

.. _list:
List
^^^^

This question type prompts the agent to format the response as a list of items.

.. code-block:: python

    from edsl.questions import QuestionList

    q_li = QuestionList(
        question_name = "q_li",
        question_text = "What improvements would you like to see in clothing options for tall women?"
    )

.. _numerical:
Numerical
^^^^^^^^^

This question type prompts the agent to format the response as a number.

.. code-block:: python

    from edsl.questions import QuestionNumerical

    q_nu = QuestionNumerical(
        question_name = "q_nu",
        question_text = "Estimate the amount of money that you spent on clothing in the past year (in $USD)."
    )

.. _administering_questions_surveys:
Administering questions & surveys
---------------------------------

Here we show how to administer each question to the default LLM. 
We do this by appending the `run()` method to a question. 
See also how to administer questions and surveys to specific agent personas and LLMs in 
example 
`Agents <https://deepnote.com/workspace/expected-parrot-c2fa2435-01e3-451d-ba12-9c36b3b87ad9/project/Expected-Parrot-examples-b457490b-fc5d-45e1-82a5-a66e1738a4b9/notebook/Docs%20-%20Agents-7b70a3e973754f18b791250db5bd7933>`__
and 
`Surveys <https://deepnote.com/workspace/expected-parrot-c2fa2435-01e3-451d-ba12-9c36b3b87ad9/project/Expected-Parrot-examples-b457490b-fc5d-45e1-82a5-a66e1738a4b9/notebook/Docs%20-%20Surveys-e6a1c6b358e4473289d97fa377002cd6>`__
.

.. _administer_question:
Administer a question independently
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    result_mc = q_mc.run()
    result_cb = q_cb.run()
    result_ls = q_ls.run()
    result_yn = q_yn.run()
    result_bg = q_bg.run()
    result_ft = q_ft.run()
    result_li = q_li.run()
    result_nu = q_nu.run()

We can select the fields to inspect (e.g., just the response):

.. code-block:: python 

    result_mc.select("q_mc").print()
    result_cb.select("q_cb").print()
    result_ls.select("q_ls").print()
    result_yn.select("q_yn").print()
    result_bg.select("q_bg").print()
    result_ft.select("q_ft").print()
    result_li.select("q_li").print()
    result_nu.select("q_nu").print()


.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answer     </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_mc      </span>┃
    ┡━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Seasonally </span>│
    └────────────┘
    </pre>




.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answer                                             </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_cb                                              </span>┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ['Quality', 'Style and Design', 'Fit and Comfort'] </span>│
    └────────────────────────────────────────────────────┘
    </pre>




.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answer </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_ls  </span>┃
    ┡━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 4      </span>│
    └────────┘
    </pre>




.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answer </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_yn  </span>┃
    ┡━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Yes    </span>│
    └────────┘
    </pre>




.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answer                                                                                                 </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_bg                                                                                                  </span>┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> [{'Online': 30}, {'Malls': 20}, {'Freestanding stores': 40}, {'Mail order catalogs': 5}, {'Other': 5}] </span>│
    └────────────────────────────────────────────────────────────────────────────────────────────────────────┘
    </pre>




.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answer                                                                                                          </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_ft                                                                                                           </span>┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> As a tall woman, I would like to see more options for longer inseams on pants and sleeves on tops. It would     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> also be great to have more variety in styles that are specifically designed for taller frames, such as dresses  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> with longer torsos and jumpsuits with longer straps.                                                            </span>│
    └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
    </pre>




.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answer                                                                                                          </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_li                                                                                                           </span>┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ['more variety in inseam lengths', 'trendy styles in tall sizes', 'better proportioned sleeves and torso        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> lengths']                                                                                                       </span>│
    └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
    </pre>




.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answer </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_nu  </span>┃
    ┡━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 1200   </span>│
    └────────┘
    </pre>



We can add some pretty labels to our tables:


.. code:: 

    result_mc.select("q_mc").print(pretty_labels={"answer.q_mc":q_mc.question_text})
    result_cb.select("q_cb").print(pretty_labels={"answer.q_cb":q_cb.question_text})
    result_ls.select("q_ls").print(pretty_labels={"answer.q_ls":q_ls.question_text})
    result_yn.select("q_yn").print(pretty_labels={"answer.q_yn":q_yn.question_text})
    result_bg.select("q_bg").print(pretty_labels={"answer.q_bg":q_bg.question_text})
    result_ft.select("q_ft").print(pretty_labels={"answer.q_ft":q_ft.question_text})
    result_li.select("q_li").print(pretty_labels={"answer.q_li":q_li.question_text})
    result_nu.select("q_nu").print(pretty_labels={"answer.q_nu":q_nu.question_text})



.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> How often do you shop for clothes? </span>┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Seasonally                         </span>│
    └────────────────────────────────────┘
    </pre>




.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> Which of the following factors are important to you in making decisions about clothes shopping? Select all that </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> apply                                                                                                           </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .                                                                                                               </span>┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ['Quality', 'Style and Design', 'Fit and Comfort']                                                              </span>│
    └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
    </pre>




.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> On a scale of 0-10, how much do you typically enjoy clothes shopping? (0 = Not at all, 10 = Very much) </span>┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 4                                                                                                      </span>│
    └────────────────────────────────────────────────────────────────────────────────────────────────────────┘
    </pre>




.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> Have you ever felt excluded or frustrated by the standard sizes of the fashion industry? </span>┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Yes                                                                                      </span>│
    └──────────────────────────────────────────────────────────────────────────────────────────┘
    </pre>




.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> Estimate the percentage of your total time spent shopping for clothes in each of the following modes   </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .                                                                                                      </span>┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> [{'Online': 30}, {'Malls': 20}, {'Freestanding stores': 40}, {'Mail order catalogs': 5}, {'Other': 5}] </span>│
    └────────────────────────────────────────────────────────────────────────────────────────────────────────┘
    </pre>




.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> What improvements would you like to see in clothing options for tall women?                                     </span>┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> As a tall woman, I would like to see more options for longer inseams on pants and sleeves on tops. It would     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> also be great to have more variety in styles that are specifically designed for taller frames, such as dresses  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> with longer torsos and jumpsuits with longer straps.                                                            </span>│
    └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
    </pre>




.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> What improvements would you like to see in clothing options for tall women?                                     </span>┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ['more variety in inseam lengths', 'trendy styles in tall sizes', 'better proportioned sleeves and torso        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> lengths']                                                                                                       </span>│
    └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
    </pre>




.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> Estimate the amount of money that you spent on clothing in the past year (in $USD) </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .                                                                                  </span>┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 1200                                                                               </span>│
    └────────────────────────────────────────────────────────────────────────────────────┘
    </pre>



.. _construct_survey:
Combine questions into a survey
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We can also combine the questions into a survey and administer them asynchronously (by default):

.. code-block:: python
    
    from edsl import Survey
    survey = Survey([q_mc, q_cb, q_ls, q_yn, q_bg, q_ft, q_li, q_nu])
    results = survey.run()
    results.select("answer.*").print()

.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━┳━━━━━━━┳━━━━━━━┳━━━━━━┳━━━━━━━┳━━━━━━┳━━━━━━━┳━━━━━━┳━━━━━━━┳━━━━━━┳━━━━━━━┳━━━━━━┳━━━━━━━┳━━━━━━┳━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answ… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answ… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answ… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> ans… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answ… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> ans… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answ… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> ans… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answ… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> ans… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answ… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> ans… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answ… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> ans… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answ… </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_l… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_li </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_nu </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_c… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_cb </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_y… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_mc </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_m… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_l… </span>┃
    ┡━━━━━━━╇━━━━━━━╇━━━━━━━╇━━━━━━╇━━━━━━━╇━━━━━━╇━━━━━━━╇━━━━━━╇━━━━━━━╇━━━━━━╇━━━━━━━╇━━━━━━╇━━━━━━━╇━━━━━━╇━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> I     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ['mo… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 1200  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> This </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> I     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Yes  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ['Qu… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> I    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Yes,  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 4    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Seas… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> [{'… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> I     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> As a </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> As a  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> typi… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> vari… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> is   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> prio… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'Sty… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> spe… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> as an </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 30}, </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> shop  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> enjoy </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> in    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> my   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> qual… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> and   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 30%  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> agent </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'M… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> for   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> wom… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> woma… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> clot… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> inse… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> est… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> style </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Desi… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> of   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> in    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 20}, </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> clot… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> I    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> I     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> shop… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> leng… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> bas… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> and   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'Fit  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> my   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'F… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> seas… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> wou… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> would </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> to a  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'tre… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> on   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> desi… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> and   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> time </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> fash… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sto… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> usua… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> like </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> like  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> mode… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> styl… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> my   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> and   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Comf… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sho… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> indu… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 40}, </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> when  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> to   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> to    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> exte… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> in    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> clo… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> fit   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> for  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> I     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'M… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> see  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> see   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> so I  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> pur… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> and   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> clo… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> have  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ord… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> seas… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> more </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> more  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> would </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> size… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> thr… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> comf… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> onl… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> expe… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> cat… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> chan… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> opt… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> opti… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> rate  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'bet… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> when  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 20%  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> frus… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 5},  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> to    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> for  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> that  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> it as </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> prop… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> yea… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> maki… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> at   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> with  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'O… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> upda… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> lon… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> cater </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> a 4   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> slee… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> deci… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> mal… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 5}]  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> my    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ins… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> to    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> on    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> and   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> about </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 40%  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> limi… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ward… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> on   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> our   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> torso </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> clot… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> at   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sizes </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> pan… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> spec… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> scal… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> leng… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> shop… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> fre… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> avai… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> and  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> needs </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sto… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> that  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sle… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> and   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 5%   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> often </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> on   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> body  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> with </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> excl… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> top… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> prop… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> mail </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> cert… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> It   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ord… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> body  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> wou… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> cat… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> type… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> also </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> and  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> be   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 5%   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> gre… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> in   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> to   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> oth… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> have </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> way… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> more </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> var… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> in   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sty… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> that </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> are  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> spe… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> des… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> for  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tal… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> fra… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> such </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> as   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> dre… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> with </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> lon… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tor… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> and  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> jum… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> with </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> lon… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> str… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│
    └───────┴───────┴───────┴──────┴───────┴──────┴───────┴──────┴───────┴──────┴───────┴──────┴───────┴──────┴───────┘
    </pre>


.. _parameterizing_questions:
Parameterizing questions
------------------------

We can create variations of questions by parameterizing them using the ``Scenario`` class.
Here we create versions of the free text question with a list of scenarios: 

.. code-block:: python

    from edsl import Scenario
    scenarios = [Scenario({"item":i}) for i in ["clothing", "shoes", "accessories"]]
    q_mc = QuestionMultipleChoice(
        question_name = "q_mc",
        question_text = "How often do you shop for {{ item }}?",
        question_options = [
            "Rarely or never",
            "Annually",
            "Seasonally",
            "Monthly",
            "Daily"
        ]
    )
    results = q_mc.by(scenarios).run()
    results.select("scenario.*", "q_mc").print()    



.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> scenario    </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answer     </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .item       </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_mc      </span>┃
    ┡━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> clothing    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Seasonally </span>│
    ├─────────────┼────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> shoes       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Seasonally </span>│
    ├─────────────┼────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> accessories </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Seasonally </span>│
    └─────────────┴────────────┘
    </pre>


.. _filtering-results:
Filtering results
^^^^^^^^^^^^^^^^^

We can filter results by adding a logical expression to the ``select()``
method. Note that all question types other than free text automatically
include a “comment” field for the response:

.. code:: 

    (results
    .filter("scenario.item == 'shoes'")
    .select("scenario.item", "answer.*")
    .print()
    )



.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> scenario </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answer                                                                                  </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answer     </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .item    </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_mc_comment                                                                           </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_mc      </span>┃
    ┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> shoes    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> I shop for shoes seasonally, typically when the seasons change or when I need a         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Seasonally </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> specific type of shoe for a particular season.                                          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">            </span>│
    └──────────┴─────────────────────────────────────────────────────────────────────────────────────────┴────────────┘
    </pre>



.. _adding_agents:
Adding AI agents 
----------------

We use the `Agent` class to define an AI agent with a persona to reference in responding to questions:

.. code-block:: python

    from edsl import Agent
    agent = Agent(name = "Fashion expert", traits = {"persona": "You are an expert in fashion design."})
    
We assign the agent to the survey with the `by()` method:

.. code-block:: python

    results = survey.by(agent).run()
    results.select("persona", "answer.q_ft").print()



.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> agent                                </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answer                                                                   </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .persona                             </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_ft                                                                    </span>┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> You are an expert in fashion design. </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> As an expert in fashion design, I would like to see more options for     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall women that cater to their specific needs. This could include longer </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> inseams on pants, longer sleeves on tops and jackets, and dresses and    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> skirts with longer hemlines. Additionally, more variety in styles and    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> cuts that are designed to flatter taller figures would be great to see   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> in the market.                                                           </span>│
    └──────────────────────────────────────┴──────────────────────────────────────────────────────────────────────────┘
    </pre>



.. _add_memory:
Add question/answer memory
^^^^^^^^^^^^^^^^^^^^^^^^^^

We can include a “memory” of a prior question/answer in the prompt for a
subsequent question. Here we include the question and response to q_mc
in the prompt for q_ft and inspect it:

.. code-block:: python

    survey.add_targeted_memory(q_li, q_ft)
    
    results = survey.by(agent).run()
    (results
    .select("q_li", "q_ft_user_prompt", "q_ft")
    .print({
        "answer.q_li": "(List version) " + q_li.question_text, 
        "prompt.q_ft_user_prompt": "Prompt for q_ft",
        "answer.q_ft": "(Free text version) " + q_ft.question_text
        }) 
    )



.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> (List version) What improvements    </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> (Free text version) What            </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold">                                     </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> would you like to see in clothing   </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> improvements would you like to see  </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold">                                     </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> options for tall women?             </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> in clothing options for tall women? </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> Prompt for q_ft                     </span>┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ['Longer inseams on pants', 'Longer </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> As an expert in fashion design, I   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'text': 'You are being asked the   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sleeves on tops and jackets',       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> would like to see more options for  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> following question: What            </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'Dresses and skirts with longer     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall women that cater to their      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> improvements would you like to see  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hemlines', 'More variety in styles  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> specific needs. This could include  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> in clothing options for tall        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> and cuts for taller figures']       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> longer inseams on pants, longer     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> women?\nReturn a valid JSON         </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sleeves on tops and jackets, and    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> formatted like this:\n{"answer":    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> dresses and skirts with longer      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> "&lt;put free text answer here&gt;"}',    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hemlines. Additionally, more        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'class_name': 'FreeText'}           </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> variety in styles and cuts that are </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> designed to flatter taller figures  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> would be great to see in the        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> market.                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                     </span>│
    └─────────────────────────────────────┴─────────────────────────────────────┴─────────────────────────────────────┘
    </pre>


.. _specify-llms:
Specifying LLMs
---------------

We can specify the language models to use in running a survey:

.. code:: 

    from edsl import Model 
    
    Model.available()




.. parsed-literal::

    ['gpt-3.5-turbo',
     'gpt-4-1106-preview',
     'gemini_pro',
     'llama-2-13b-chat-hf',
     'llama-2-70b-chat-hf',
     'mixtral-8x7B-instruct-v0.1']



.. code:: 

    models = [Model(m) for m in ['gpt-3.5-turbo', 'gpt-4-1106-preview']]
    
    results = survey.by(agent).by(models).run()
    results.select("model.model", "q_bg", "q_li").print()



.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> model              </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answer                                       </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answer                                      </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .model             </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_bg                                        </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_li                                       </span>┃
    ┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> gpt-3.5-turbo      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> [{'Online': 30}, {'Malls': 20},              </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ['Longer inseams on pants', 'Longer sleeves </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'Freestanding stores': 40}, {'Mail order    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> on tops and jackets', 'Dresses and skirts   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> catalogs': 5}, {'Other': 5}]                 </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> with longer hemlines', 'More variety in     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                              </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> styles and cuts for taller figures']        </span>│
    ├────────────────────┼──────────────────────────────────────────────┼─────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> gpt-4-1106-preview </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> [{'Online': 40}, {'Malls': 30},              </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ['Proportional sizing', 'Extended sleeve    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'Freestanding stores': 20}, {'Mail order    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> lengths', 'Trendy styles in tall sections', </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> catalogs': 5}, {'Other': 5}]                 </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'Variety in inseam lengths', 'Longer skirts </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                              </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> and dresses', 'Larger shoe size options']   </span>│
    └────────────────────┴──────────────────────────────────────────────┴─────────────────────────────────────────────┘
    </pre>



Show columns
^^^^^^^^^^^^

We can check a list all of the components of the results with the
``columns`` method:

.. code:: 

    results = q_mc.by(scenarios).by(agent).by(models).run()
    results.columns




.. parsed-literal::

    ['agent.agent_name',
     'agent.persona',
     'answer.q_mc',
     'answer.q_mc_comment',
     'model.frequency_penalty',
     'model.max_tokens',
     'model.model',
     'model.presence_penalty',
     'model.temperature',
     'model.top_p',
     'model.use_cache',
     'prompt.q_mc_system_prompt',
     'prompt.q_mc_user_prompt',
     'raw_model_response.q_mc_raw_model_response',
     'scenario.item']



--------------

.. raw:: html

   <p style="font-size: 14px;">

Copyright © 2024 Expected Parrot, Inc. All rights reserved.
www.expectedparrot.com



