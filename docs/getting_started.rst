Getting started with EDSL
=========================

The Expected Parrot Domain-Specifc Language (EDSL) library is a
collection of tools for conducting surveys and experiments with AI
agents. This page provides a series of examples for the basic EDSL
functions:

-  We create questions using the ``Question`` class and subclasses for
   different question types (multiple choice, free text, etc.).
-  We combine questions into surveys using the ``Survey`` class and
   specify survey logic and question parameters (``Scenario`` objects).
-  We design AI agents with personas representing survey respondents
   using the ``Agent`` class.
-  We select language models to use in simulating survey responses from
   agents using the ``Model`` class.
-  We administer surveys and explore the results using ``Results`` class
   methods for analysis and visualization.

Installation
------------

The EDSL library is available on PyPI: https://pypi.org/project/edsl/.

Before beginning this tutorial, see details on requirements and
instructions on installing the EDSL library here.

Learn more
----------

-  This page is available as an interactive python notebook here.
-  See our Showcase of notebooks and templates exploring use cases and
   ideas for conducting research using EDSL.
-  Learn more about the EDSL libary in the EDSL Docs.

Contents
--------

-  `Creating a survey <#creating-a-survey>`__
-  `Question types <#question-types>`__
-  `Survey logic <#survey-logic>`__
-  `Scenarios <#scenarios>`__
-  `Agents <#agents>`__
-  `Models <#models>`__
-  `Exploring results <#exploring-results>`__

Creating a survey
-----------------

We start by creating some survey questions. The EDSL library provides a
variety of question types with different formats as subclassess of the
``Question`` class.

-  All questions require a unique question name and a question text.
-  Question types other than free text and yes/no also require a list of
   answer options.

Select a question type based on the form of the response that you want
to receive. For example, ``QuestionFreeText`` will return an
unstructured textual response and ``QuestionMultipleChoice`` will return
a single selection from a specified list of options. This is done by
prompting the agent to respond to the question in the required format.
We cover some details about prompts in the section on `Exploring
results <#exploring-results>`__.

Question types
~~~~~~~~~~~~~~

Here we import each question type and show an example question in the
required format:

Multiple choice
^^^^^^^^^^^^^^^

A multiple choice question prompts the agent to select one of the answer
options.

.. code:: python

    from edsl.questions import QuestionMultipleChoice
    
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

Checkbox
^^^^^^^^

A checkbox question requires the agent to select one or more of the
answer options, which are returned as a list. The minimum and maximum
number of options that may be selected are optional.

.. code:: python

    from edsl.questions import QuestionCheckBox
    
    q_cb = QuestionCheckBox(
        question_name = "q_cb",
        question_text = """Which of the following factors are important to you in making decisions 
        about clothes shopping? Select all that apply.""",
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
        min_selections = 1, # optional
        max_selections = 3  # optional
    )

Free text
^^^^^^^^^

A free text question prompts the agent to respond with unstructured
text.

.. code:: python

    from edsl.questions import QuestionFreeText
    
    q_ft = QuestionFreeText(
        question_name = "q_ft",
        question_text = "What improvements would you like to see in options for clothes shopping?"
    )

Linear scale
^^^^^^^^^^^^

A linear scale question prompts the agent to select one of the answer
options which are a list of integers.

.. code:: python

    from edsl.questions import QuestionLinearScale
    
    q_ls = QuestionLinearScale(
        question_name = "q_ls",
        question_text = """On a scale of 0-10, how much do you typically enjoy clothes shopping? 
        (0 = Not at all, 10 = Very much)""",
        question_options = [0,1,2,3,4,5,6,7,8,9,10]
    )

Numerical
^^^^^^^^^

A numerical question prompts the agent to respond with a number.

.. code:: python

    from edsl.questions import QuestionNumerical
    
    q_nu = QuestionNumerical(
        question_name = "q_nu",
        question_text = """Estimate the amount of money that you spent shopping for clothes in 
        the past year (in $USD)."""
    )

List
^^^^

A list question prompts the agent to provide a response in the form of a
list.

.. code:: python

    from edsl.questions import QuestionList
    
    q_li = QuestionList(
        question_name = "q_li",
        question_text = "What improvements would you like to see in options for clothes shopping?"
    )

Budget
^^^^^^

A budget question prompts the agent to allocation a sum among the answer
options and respond with a dictionary where the keys are the answer
options and the values are the allocated amounts.

.. code:: python

    from edsl.questions import QuestionBudget
    
    q_bg = QuestionBudget(
        question_name = "q_bg",
        question_text = """Estimate the percentage of your total time spent shopping for clothes 
        in each of the following modes.""",
        question_options=[
            "Online",
            "Malls",
            "Freestanding stores",
            "Mail order catalogs",
            "Other"
        ],
        budget_sum = 100,
    )

Yes / No
^^^^^^^^

A yes/no question prompts the agent to respond with a yes or no. The
answer options are pre-set. Use a multiple choice or other appropriate
type if you want to include other options (e.g., “I don’t know”).

.. code:: python

    from edsl.questions import QuestionYesNo
    
    q_yn = QuestionYesNo(
        question_name = "q_yn",
        question_text = "Have you ever felt excluded or frustrated by options for clothes shopping?", 
    )

Survey logic
~~~~~~~~~~~~

We combine questions into a survey using the ``Survey`` class. A
``Survey`` object is created with a list of one or more questions:

.. code:: python

    from edsl import Survey 
    
    clothes_shopping_survey = Survey(questions = [q_mc, q_cb, q_ft, q_ls, q_nu, q_li, q_bg, q_yn])

By default, questions are delivered asynchronously to agents when we run
a survey. We can specify different survey logic with the
``add_stop_rule`` and ``add_targeted_memory`` methods.

Stop/skip logic
^^^^^^^^^^^^^^^

Here we create a survey with 2 questions and apply a rule to skip the
second question based on a negative response to the first question. We
can use any rule that can be expressed as a logical statement. The form
of the method is
``Survey.add_stop_rule(question_name, <logical expression>)``:

.. code:: python

    q1 = QuestionYesNo(
        question_name = "enjoy",
        question_text = "Do you enjoy clothes shopping?"
    )
    q2 = QuestionLinearScale(
        question_name = "enjoy_scale",
        question_text = """On a scale of 0-10, how much do you typically enjoy clothes shopping? 
        (0 = Not at all, 10 = Very much)""",
        question_options = [0,1,2,3,4,5,6,7,8,9,10]
    )
    survey = Survey(questions = [q1, q2])
    survey.add_stop_rule("enjoy", "enjoy == 'No'")




.. parsed-literal::

    Survey(questions=[QuestionYesNo(question_text = 'Do you enjoy clothes shopping?', question_options = ['Yes', 'No'], question_name = 'enjoy', short_names_dict = {}), QuestionLinearScale(question_text = 'On a scale of 0-10, how much do you typically enjoy clothes shopping? 
        (0 = Not at all, 10 = Very much)', question_options = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], question_name = 'enjoy_scale', short_names_dict = {}, option_labels = None)], name=None)



Question memory
^^^^^^^^^^^^^^^

The ``add_targeted_memory`` method lets us change the default
asynchronous behavior of the survey and selectively include questions
and responses in subsequent question prompts as agent memories. Here we
add the question and response for the first question to the prompt for
the second question:

.. code:: python

    survey.add_targeted_memory(q2, q1)

Note that we can specify the question names or ids as the arguments to
the ``add_targeted_memory`` method. The following command is equivalent:

.. code:: python

    survey.add_targeted_memory("enjoy_scale", "enjoy")

We can do this as many times as desired to add multiple prior questions
and answers to the prompt for a subsequent question (we show how to
examine the prompts below in `Prompts <#prompts>`__). Here we add 2
prior questions and responses to a question:

.. code:: python

    q3 = QuestionFreeText(
        question_name = "pros_cons",
        question_text = "What are some pros and cons of online clothes shopping?"
    )
    survey = Survey([q1, q2, q3])
    survey.add_targeted_memory(q3, q1)
    survey.add_targeted_memory(q3, q2)

Scenarios
~~~~~~~~~

We can parameterize our questions in order to create different versions
of “scenarios” of them using the ``Scenario`` class. Here we create a
question with a parameter and then create scenarios for the parameter
values that we want to use in the survey:

.. code:: python

    from edsl import Scenario
    
    q = QuestionFreeText(
        question_name = "favorite",
        question_text = "Describe your favorite {{ item }}."
    )
    
    scenarios = [Scenario({"item": i}) for i in ["t-shirt", "hat", "sweater"]]

Scenarios are applied to a survey using the ``by`` method. This allows
the scenarios to be applied to all questions in the survey that take the
same parameters. We typically wait to do this until we are administering
the survey using the ``run`` method:

.. code:: python

    results = q.by(scenarios).run()

Note that we can administer a single question individually because the
``run`` method automatically converts it into a ``Survey`` object for
convenience. The following commands will yield an identical result to
the command above:

.. code:: python

    survey = Survey([q])
    results = survey.by(scenarios).run()

Agents
~~~~~~

We can create personas and traits for the AI agents that will respond to
our survey with the ``Agent`` class. An ``Agent`` object takes an
optional ``name`` and a (required) set of ``traits`` in the form of a
dictionary. We can use the ``example`` method to see an example:

.. code:: python

    from edsl import Agent 
    
    Agent.example()




.. parsed-literal::

    Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5})



Here we create a single agent with a name and a short persona
description:

.. code:: python

    agent = Agent(
        name = "Agent_shopper", 
        traits = {"persona": "You are a 45-year-old woman who prefers to shop online."}
        )
    agent




.. parsed-literal::

    Agent(name = 'Agent_shopper', traits = {'persona': 'You are a 45-year-old woman who prefers to shop online.'})



Here we use lists of traits to create a panel of agents with
combinations of the dimensions. For convenience in analyzing results by
agent traits later on (e.g., by agent age), we can include the trait
dimensions both individually and as part of the persona narrative:

.. code:: python

    base_persona = "You are a {age}-year-old {height} woman who prefers to shop online."
    ages = [25, 45, 65,]
    heights = ["short", "average", "tall"]
    
    agents = [Agent(traits = {
        "persona": base_persona.format(age = age, height = height),
        "age": age,
        "height": height
        }) for age in ages for height in heights]
    agents




.. parsed-literal::

    [Agent(traits = {'persona': 'You are a 25-year-old short woman who prefers to shop online.', 'age': 25, 'height': 'short'}),
     Agent(traits = {'persona': 'You are a 25-year-old average woman who prefers to shop online.', 'age': 25, 'height': 'average'}),
     Agent(traits = {'persona': 'You are a 25-year-old tall woman who prefers to shop online.', 'age': 25, 'height': 'tall'}),
     Agent(traits = {'persona': 'You are a 45-year-old short woman who prefers to shop online.', 'age': 45, 'height': 'short'}),
     Agent(traits = {'persona': 'You are a 45-year-old average woman who prefers to shop online.', 'age': 45, 'height': 'average'}),
     Agent(traits = {'persona': 'You are a 45-year-old tall woman who prefers to shop online.', 'age': 45, 'height': 'tall'}),
     Agent(traits = {'persona': 'You are a 65-year-old short woman who prefers to shop online.', 'age': 65, 'height': 'short'}),
     Agent(traits = {'persona': 'You are a 65-year-old average woman who prefers to shop online.', 'age': 65, 'height': 'average'}),
     Agent(traits = {'persona': 'You are a 65-year-old tall woman who prefers to shop online.', 'age': 65, 'height': 'tall'})]



Agents are assigned to a survey using the ``by`` method. Similar to
scenarios, this will administer all questions to each agent. We also
typically wait to do this until we are administering the survey using
the ``run`` method:

.. code:: python

    results = survey.by(scenarios).by(agents).run()

It does not matter which order we use the ``by`` method to add the
scenarios and agents. The following command will yield an identical
result as the command above:

.. code:: python

    results = survey.by(agents).by(scenarios).run()

However, if agents or scenarios are created independently they must be
combined in the same ``by`` method call as a list. For example, we could
create agents separately and then combine them in a list:

.. code:: python

    agent_1 = Agent(traits = {"persona": "You are a 45-year-old woman who prefers to shop online."})
    agent_2 = Agent(traits = {"persona": "You are a 25-year-old man who prefers to shop in person."})
    
    results = survey.by(scenarios).by([agent_1, agent_2]).run()

Note that if an agent name is not specified when the ``Agent`` object is
created, an ``agent_name`` field is automatically created when survey
results are generated. We will see this when we inspect results in the
next sections.

Models
~~~~~~

We use the ``Model`` class to specify the language models that we want
to use in simulating survey results. The default model is GPT-4 (if we
do not specify a model - as in the above examples - the results are
generated using the default model). We can use the ``available`` method
to see a list of available models:

.. code:: python

    from edsl import Model
    
    Model.available()




.. parsed-literal::

    ['gpt-3.5-turbo',
     'gpt-4-1106-preview',
     'gemini_pro',
     'llama-2-13b-chat-hf',
     'llama-2-70b-chat-hf',
     'mixtral-8x7B-instruct-v0.1']



Here we create a list of models to call in running the survey - results
will be generated using each of them:

.. code:: python

    models = [Model(m) for m in ["gpt-3.5-turbo", "gpt-4-1106-preview"]]

We can call the objects to see all of the parameters that we might
choose to adjust (e.g., temperature):

.. code:: python

    models




.. parsed-literal::

    [LanguageModelOpenAIThreeFiveTurbo(model = 'gpt-3.5-turbo', parameters={'temperature': 0.5, 'max_tokens': 1000, 'top_p': 1, 'frequency_penalty': 0, 'presence_penalty': 0, 'use_cache': True}),
     LanguageModelOpenAIFour(model = 'gpt-4-1106-preview', parameters={'temperature': 0.5, 'max_tokens': 1000, 'top_p': 1, 'frequency_penalty': 0, 'presence_penalty': 0, 'use_cache': True})]



Models are also assigned to a survey using the ``by`` method. We
typically wait to do this until we are administering the survey using
the ``run`` method:

.. code:: python

    results = survey.by(scenarios).by(agents).by(models).run()

Exporing results
----------------

We can reference the components of the results with the ``columns``
method. This command will return a list of all the fields in the results
that may be selected individually:

.. code:: python

    results.columns




.. parsed-literal::

    ['agent.age',
     'agent.agent_name',
     'agent.height',
     'agent.persona',
     'answer.favorite',
     'model.frequency_penalty',
     'model.max_tokens',
     'model.model',
     'model.presence_penalty',
     'model.temperature',
     'model.top_p',
     'model.use_cache',
     'prompt.favorite_system_prompt',
     'prompt.favorite_user_prompt',
     'raw_model_response.favorite_raw_model_response',
     'scenario.item']



We can do the same for our clothes shopping survey and see the question-
and agent-specific components of the results:

.. code:: python

    results_shopping = clothes_shopping_survey.by(agents).by(models).run()
    results_shopping.columns




.. parsed-literal::

    ['agent.age',
     'agent.agent_name',
     'agent.height',
     'agent.persona',
     'answer.q_bg',
     'answer.q_bg_comment',
     'answer.q_cb',
     'answer.q_cb_comment',
     'answer.q_ft',
     'answer.q_li',
     'answer.q_li_comment',
     'answer.q_ls',
     'answer.q_ls_comment',
     'answer.q_mc',
     'answer.q_mc_comment',
     'answer.q_nu',
     'answer.q_nu_comment',
     'answer.q_yn',
     'answer.q_yn_comment',
     'model.frequency_penalty',
     'model.max_tokens',
     'model.model',
     'model.presence_penalty',
     'model.temperature',
     'model.top_p',
     'model.use_cache',
     'prompt.q_bg_system_prompt',
     'prompt.q_bg_user_prompt',
     'prompt.q_cb_system_prompt',
     'prompt.q_cb_user_prompt',
     'prompt.q_ft_system_prompt',
     'prompt.q_ft_user_prompt',
     'prompt.q_li_system_prompt',
     'prompt.q_li_user_prompt',
     'prompt.q_ls_system_prompt',
     'prompt.q_ls_user_prompt',
     'prompt.q_mc_system_prompt',
     'prompt.q_mc_user_prompt',
     'prompt.q_nu_system_prompt',
     'prompt.q_nu_user_prompt',
     'prompt.q_yn_system_prompt',
     'prompt.q_yn_user_prompt',
     'raw_model_response.q_bg_raw_model_response',
     'raw_model_response.q_cb_raw_model_response',
     'raw_model_response.q_ft_raw_model_response',
     'raw_model_response.q_li_raw_model_response',
     'raw_model_response.q_ls_raw_model_response',
     'raw_model_response.q_mc_raw_model_response',
     'raw_model_response.q_nu_raw_model_response',
     'raw_model_response.q_yn_raw_model_response']



Note that each question type other than free text also automatically
includes a ``_comment`` field where the agent is allowed to provide
unstructed textual commentary in addition to its required formatted
response. We’ll show how to access these fields in the next sections.

Printing
~~~~~~~~

We can use some print methods to display results in readable formats.
The ``print_long`` method displays the components vertically. Here we do
this for the first of our results:

.. code:: python

    results[:1].print_long()



.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace"><span style="font-style: italic">        Scenario Attributes        </span>
    ┏━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="font-weight: bold"> Attribute </span>┃<span style="font-weight: bold"> Value               </span>┃
    ┡━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="font-weight: bold"> data      </span>│<span style="font-weight: bold"> {'item': 't-shirt'} </span>│
    └───────────┴─────────────────────┘
    </pre>




.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> Key                         </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> Value                                                                             </span>┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> persona                     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> You are a 25-year-old short woman who prefers to shop online.                     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> age                         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25                                                                                </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> height                      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short                                                                             </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> agent_name                  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Agent_0                                                                           </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> agent                       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'persona': 'You are a 25-year-old short woman who prefers to shop online.',      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'age': 25, 'height': 'short', 'agent_name': 'Agent_0'}                            </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> item                        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt                                                                           </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> scenario                    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         Scenario Attributes                                                       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ┏━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓                                               </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ┃ Attribute ┃ Value               ┃                                               </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ┡━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩                                               </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> │ data      │ {'item': 't-shirt'} │                                               </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> └───────────┴─────────────────────┘                                               </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                                                                   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> temperature                 </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 0.5                                                                               </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> max_tokens                  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 1000                                                                              </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> top_p                       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 1                                                                                 </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> frequency_penalty           </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 0                                                                                 </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> presence_penalty            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 0                                                                                 </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> use_cache                   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> True                                                                              </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> model                       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'temperature': 0.5, 'max_tokens': 1000, 'top_p': 1, 'frequency_penalty': 0,      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'presence_penalty': 0, 'use_cache': True, 'model': 'gpt-3.5-turbo'}               </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> favorite                    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a cozy oversized black shirt with a cute graphic design on </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the front. It's super comfortable and goes well with any pair of jeans or         </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> leggings.                                                                         </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> answer                      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'favorite': "My favorite t-shirt is a cozy oversized black shirt with a cute     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> graphic design on the front. It's super comfortable and goes well with any pair   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> of jeans or leggings."}                                                           </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> favorite_user_prompt        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'text': 'You are being asked the following question: Describe your favorite      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt.\nReturn a valid JSON formatted like this:\n{"answer": "&lt;put free text    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> answer here&gt;"}', 'class_name': 'FreeText'}                                        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> favorite_system_prompt      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'text': "You are answering questions as if you were a human. Do not break        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> character. You are an agent with the following persona:\n{'persona': 'You are a   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25-year-old short woman who prefers to shop online.', 'age': 25, 'height':        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'short'}", 'class_name': 'AgentInstruction'}                                      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> prompt                      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'favorite_user_prompt': {'text': 'You are being asked the following question:    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Describe your favorite t-shirt.\nReturn a valid JSON formatted like               </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> this:\n{"answer": "&lt;put free text answer here&gt;"}', 'class_name': 'FreeText'},     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'favorite_system_prompt': {'text': "You are answering questions as if you were a  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> human. Do not break character. You are an agent with the following                </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> persona:\n{'persona': 'You are a 25-year-old short woman who prefers to shop      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> online.', 'age': 25, 'height': 'short'}", 'class_name': 'AgentInstruction'}}      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> favorite_raw_model_response </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'id': 'chatcmpl-92jmAHnZrytxfxyVVHh0FqWqefVdc', 'choices': [{'finish_reason':    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'stop', 'index': 0, 'logprobs': None, 'message': {'content': '{"answer": "My      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> favorite t-shirt is a cozy oversized black shirt with a cute graphic design on    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the front. It\'s super comfortable and goes well with any pair of jeans or        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> leggings."}', 'role': 'assistant', 'function_call': None, 'tool_calls': None}}],  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'created': 1710439646, 'model': 'gpt-3.5-turbo-0125', 'object':                   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'chat.completion', 'system_fingerprint': 'fp_4f2ebda25a', 'usage':                </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'completion_tokens': 39, 'prompt_tokens': 100, 'total_tokens': 139,              </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'cached_response': None, 'elapsed_time': 0.1339116096496582, 'timestamp':         </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 1710446989.3507679}, 'elapsed_time': 0.1339116096496582, 'timestamp':             </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 1710446989.3507679, 'cached_response': True}                                      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> raw_model_response          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'favorite_raw_model_response': {'id': 'chatcmpl-92jmAHnZrytxfxyVVHh0FqWqefVdc',  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'choices': [{'finish_reason': 'stop', 'index': 0, 'logprobs': None, 'message':    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'content': '{"answer": "My favorite t-shirt is a cozy oversized black shirt with </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> a cute graphic design on the front. It\'s super comfortable and goes well with    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> any pair of jeans or leggings."}', 'role': 'assistant', 'function_call': None,    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'tool_calls': None}}], 'created': 1710439646, 'model': 'gpt-3.5-turbo-0125',      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'object': 'chat.completion', 'system_fingerprint': 'fp_4f2ebda25a', 'usage':      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'completion_tokens': 39, 'prompt_tokens': 100, 'total_tokens': 139,              </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'cached_response': None, 'elapsed_time': 0.1339116096496582, 'timestamp':         </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 1710446989.3507679}, 'elapsed_time': 0.1339116096496582, 'timestamp':             </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 1710446989.3507679, 'cached_response': True}}                                     </span>│
    └─────────────────────────────┴───────────────────────────────────────────────────────────────────────────────────┘
    </pre>



The basic ``print`` method displays components horizontally, which can
be unwieldy when we do this for all components at once, even for a
survey consisting of a single question (we show how to narrow the set of
components displayed in next steps):

.. code:: python

    results[:1].print()



.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━┳━━━━━━┳━━━━━━┳━━━━━━┳━━━━━━┳━━━━━━┳━━━━━━┳━━━━━━┳━━━━━━┳━━━━━━┳━━━━━━┳━━━━━━┳━━━━━━━┳━━━━━━┳━━━━━━━┳━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> ans… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> sce… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> age… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> age… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> age… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> age… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> mod… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> mod… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> mod… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> mod… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> mod… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> mod… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> model </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> pro… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> prom… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> raw… </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .fa… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .it… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .he… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .pe… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .age </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .ag… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .mo… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .ma… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .pr… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .to… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .fr… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .us… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .tem… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .fa… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .fav… </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .fa… </span>┃
    ┡━━━━━━╇━━━━━━╇━━━━━━╇━━━━━━╇━━━━━━╇━━━━━━╇━━━━━━╇━━━━━━╇━━━━━━╇━━━━━━╇━━━━━━╇━━━━━━╇━━━━━━━╇━━━━━━╇━━━━━━━╇━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-s… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sho… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> You  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Age… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> gpt… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 1000 </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 0    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 1    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 0    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> True </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 0.5   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'t… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'te… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'i… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> fav… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> are  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> "You </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'You  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'ch… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-s… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> a    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> are  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> are   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'ch… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> is a </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25-… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ans… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> being </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> [{'… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> cozy </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sho… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> que… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> asked </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'st… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ove… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> wom… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> as   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'in… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> bla… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> who  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> if   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> foll… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 0,   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> shi… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> pre… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> you  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ques… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'lo… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> with </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> to   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> were </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Desc… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Non… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> a    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> shop </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> a    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> your  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'me… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> cute </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> onl… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hum… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> favo… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'c… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> gra… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Do   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-sh… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> '{"… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> des… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> not  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> a     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> "My  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> on   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> bre… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> valid </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> fav… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> cha… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> JSON  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-s… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> fro… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> You  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> form… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> is a </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> It's </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> are  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> like  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> cozy </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sup… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> an   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> this… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ove… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> com… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> age… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> "&lt;put </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> bla… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> and  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> with </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> free  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> shi… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> goes </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> text  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> with </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> well </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> fol… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> answ… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> a    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> with </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> per… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> here… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> cute </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> any  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'You </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'cla… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> gra… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> pair </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> are  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'Fre… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> des… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> of   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> a    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> on   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> jea… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25-… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> or   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sho… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> fro… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> leg… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> wom… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> It\… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> who  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sup… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> pre… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> com… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> to   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> and  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> shop </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> goes </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> onl… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> well </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'ag… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> with </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25,  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> any  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'he… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> pair </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'sh… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> of   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'cl… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> jea… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'Ag… </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> or   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> leg… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'ro… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'as… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'fu… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Non… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'to… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Non… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'cr… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 171… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'mo… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'gp… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'ob… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'ch… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'sy… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'fp… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'us… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'c… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 39,  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'pr… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 100, </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'to… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 139, </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'ca… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Non… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'el… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 0.1… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'ti… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 171… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'el… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 0.1… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'ti… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 171… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'ca… </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Tru… </span>│
    └──────┴──────┴──────┴──────┴──────┴──────┴──────┴──────┴──────┴──────┴──────┴──────┴───────┴──────┴───────┴──────┘
    </pre>



Select
~~~~~~

We can use the ``select`` method together with the ``print`` method to
narrow the components of results that we display. Here we select some of
the agent parameters and the response to the (single) question in the
survey. Note that we can drop the prefixes ``agent.``, ``answer.``,
etc., in the select statement or include them for clarity. The following
commands will print the same results:

.. code:: python

    # results.select("agent.age", "agent.height", "scenario.item", "answer.favorite").print()
    results.select("age", "height", "item", "favorite").print()



.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> agent </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> agent   </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> scenario </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answer                                                                             </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .age  </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .height </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .item    </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .favorite                                                                          </span>┃
    ┡━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a cozy oversized black shirt with a cute graphic design on  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the front. It's super comfortable and goes well with any pair of jeans or          </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> leggings.                                                                          </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a soft, heather gray cotton blend that fits just right, not </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> too tight or too loose. It has a quirky print of a cat sitting in a pocket on the  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> left chest area, which always seems to catch people's attention and make them      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> smile. I love that it's versatile enough to pair with jeans for a casual look or   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> with a blazer for a more put-together outfit. Plus, it's held up really well       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> despite countless washes since I bought it online last year.                       </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a cozy knit beanie with a faux fur pom-pom on top. It's perfect </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> for keeping me warm in the winter while adding a cute touch to my outfits.         </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a cozy, slouchy beanie that I found online last winter. It's a  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> beautiful shade of teal and made from a soft, chunky knit fabric that keeps my     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> head warm without being itchy. It has a cute, oversized pom-pom on top that adds a </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> playful touch to any outfit. I love that it's both stylish and functional, and it  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> goes with almost everything in my wardrobe.                                        </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy, oversized knit in a soft pastel color. It's perfect </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> for lounging around the house or running errands on a chilly day.                  </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy, oversized knit that I found online last winter.     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> It's a lovely shade of heather gray, which makes it versatile enough to pair with  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> almost anything in my wardrobe. The material is super soft and warm, perfect for   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> those chilly days when I want to feel snug and comfortable. It has a relaxed fit,  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> with a slightly longer back that gives it a modern silhouette. The best part is    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the chunky turtleneck that keeps the wind out and adds a stylish touch. I love     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> curling up in it with a good book or wearing it for a casual day out.              </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a soft, grey graphic tee with a cute design of a cat        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> wearing sunglasses. It's super comfortable and goes well with jeans or leggings.   </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a soft, heather gray one with a relaxed fit. It has a       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> vintage-looking print of a mountain range across the chest, which reminds me of my </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> love for the outdoors. The fabric is a cotton blend, which makes it really         </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> comfortable for everyday wear, and it's held up really well despite numerous       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> washes. I love that it pairs easily with jeans or shorts, and it's my go-to for a  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> casual, yet put-together look.                                                     </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a cozy knit beanie in a neutral color that goes with            </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> everything. It keeps me warm and stylish during the colder months.                 </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a cozy, oversized beanie that I found online last winter. It's  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> a soft, chunky knit in a beautiful shade of heather gray, which goes with almost   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> everything in my wardrobe. It has a slouchy fit that makes it look effortlessly    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> stylish, and it's warm enough to keep me comfortable on the chilliest days. I love </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> that it's versatile enough to wear with a casual outfit or to add a bit of         </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> laid-back cool to something more dressed up.                                       </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy oversized knit in a soft pastel pink color. It has a </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> turtleneck and long sleeves, perfect for keeping me warm during the colder months. </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is this cozy, oversized knit that I found online last winter.  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> It's a soft shade of heather gray, which makes it really versatile and easy to     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> pair with almost anything in my wardrobe. The material is a blend of wool and      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> cashmere, so it's incredibly warm and just feels like a hug whenever I put it on.  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> It has a chunky turtleneck that keeps me snug on chilly days and the sleeves are   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> long enough to cover my hands, which I love. I also really like the ribbed cuffs   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> and hem because they add a bit of texture and detail. It's definitely my go-to     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> piece for comfort and style during the colder months.                              </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a soft, oversized white shirt with a vintage band logo on   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the front. It's super comfortable and goes well with jeans or leggings.            </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a heather gray, soft cotton blend with a relaxed fit that's </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> just perfect for casual days. It has a minimalistic design with a small,           </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> embroidered cactus on the left chest area that adds a touch of whimsy. The sleeves </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> are slightly rolled up, giving it a cool, effortless vibe. It's my go-to piece for </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> comfort and style, and I love how it pairs with almost anything from jeans to      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> skirts.                                                                            </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a wide-brimmed black fedora with a sleek design. It's perfect   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> for adding a touch of style to any outfit.                                         </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a wide-brimmed, floppy sun hat that I bought online. It's made  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> from a light, woven straw material, which makes it perfect for sunny days. The hat </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> has a black ribbon around the crown that adds a touch of elegance, and it's        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> incredibly versatile – I can wear it to the beach or pair it with a cute summer    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> dress for an outdoor lunch. It's not only stylish but also functional, as it       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> protects my face from the sun while making a fashion statement.                    </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy oversized knit in a soft gray color. It's perfect    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> for lounging around the house or running errands on chilly days.                   </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy, oversized turtleneck that comes in a soft shade of  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> heather grey. It's made from a blend of wool and cashmere, which makes it          </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> incredibly warm and soft to the touch. The sleeves are long enough to cover my     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hands, which I love, and the turtleneck part can be scrunched down or pulled up    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> over my chin for extra warmth. It has a ribbed texture that adds a bit of detail   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> to its simple design, and it's long enough to wear with leggings for a comfy,      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> casual look. I found it online last year and it's been my go-to ever since for     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> chilly days.                                                                       </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a soft, grey V-neck with a simple design of a coffee cup on </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the front. It's comfortable and goes with everything.                              </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a classic, fitted black tee with a subtle, yet elegant,     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> white floral pattern that cascades down one shoulder. It's made from a soft,       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> breathable cotton blend that has just the right amount of stretch to be            </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> comfortable without losing its shape. I love that it's versatile enough to wear    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> with jeans for a casual look or dressed up under a blazer for a more formal        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> occasion. It's been a staple in my wardrobe for years, and it's held up            </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> beautifully through countless washes. Plus, the length is just right for my short  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> stature, hitting at the hip without overwhelming my frame.                         </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a cozy knit beanie in a dark grey color with a faux fur pom pom </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> on top. It keeps me warm and stylish during the colder months.                     </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a cozy, knit beanie that I found online last winter. It's a     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> deep burgundy color, which I love because it goes with almost everything in my     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> wardrobe. The beanie is made from a soft wool blend that keeps my head warm        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> without being itchy, and it has a cute, oversized pom-pom on top that adds a bit   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> of fun to my winter outfits. It's snug but stretches just enough to fit            </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> comfortably, and it doesn't mess up my hair too much when I take it off. I always  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> get compliments on it whenever I wear it out.                                      </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy, oversized knit in a soft shade of gray. It's        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> perfect for lounging around the house or running errands on chilly days.           </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy, oversized turtleneck in a soft shade of heather     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> gray. It's made from a blend of wool and cashmere, which makes it incredibly warm  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> and soft against the skin. The sleeves are long enough to cover my hands, which I  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> love, and it has a chunky ribbed texture that adds a bit of visual interest        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> without being too loud. It's the kind of sweater that pairs well with leggings or  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> skinny jeans, and I can easily dress it up or down. It's my go-to piece for chilly </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> days when I want to feel snug and stylish at the same time.                        </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a soft, grey V-neck with a cute graphic print of a coffee   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> cup on it. It's super comfy and goes well with jeans or leggings.                  </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a soft, heather gray one that fits just right – not too     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tight, but not too loose either. It has a scoop neck that's flattering without     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> being too revealing, and the material is a breathable cotton blend that's          </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> comfortable for all-day wear. The front has a subtle, vintage-style graphic of a   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> mountain range with the words 'Explore More' written underneath, which always      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> reminds me of my love for the outdoors and adventure. I've had it for years, and   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> it's held up really well despite countless washes. It's definitely my go-to tee    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> for casual days or when I'm running errands.                                       </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a cozy knit beanie with a faux fur pom-pom on top. It keeps me  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> warm during the winter months and adds a touch of fun to my outfits.               </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a cozy, chunky knit beanie that I found online last winter.     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> It's a lovely shade of deep blue that matches well with most of my wardrobe, and   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> it has a cute, oversized pom-pom on top. It's both stylish and functional, keeping </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> my head warm during the chilly months. I love that it's made from soft,            </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> high-quality yarn, which doesn't itch or irritate my skin. I've received several   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> compliments on it and it's my go-to accessory for cold days.                       </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy, oversized knit in a beautiful shade of deep         </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> burgundy. It's perfect for lounging around the house or pairing with jeans for a   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> casual day out.                                                                    </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy, oversized cable knit in a soft cream color. It has  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> a chunky turtleneck that keeps me warm during chilly days and long sleeves that I  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> can pull over my hands. It's made from a blend of wool and cashmere, which makes   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> it incredibly soft to the touch and comfortable for all-day wear. I love pairing   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> it with leggings or skinny jeans and boots for a casual, yet put-together look.    </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a soft, gray V-neck with a subtle floral pattern. It's      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> comfortable and versatile, perfect for lounging at home or running errands.        </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a soft, vintage-style charcoal gray one that has a classic  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> rock band's logo on the front. It's slightly oversized, which makes it perfect for </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> a relaxed look, and the cotton material has worn in so well over the years that it </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> feels like a second skin. I love pairing it with jeans and sneakers for a casual   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> day out or lounging at home. It's my go-to piece for comfort and a touch of        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> nostalgia.                                                                         </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a wide-brimmed straw hat that I bought online. It's perfect for </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sunny days and adds a touch of style to any outfit.                                </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a sleek, wide-brimmed fedora that I found on a boutique website </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> a few years ago. It's a beautiful shade of navy blue that seems to go with         </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> everything, and the material is a soft, felted wool that feels luxurious to the    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> touch. It has a subtle, leather band around the base of the crown that adds just   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the right amount of detail without being too flashy. It's my go-to for sunny days  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> or when I want to add a touch of elegance to my outfit.                            </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy oversized knit in a soft shade of grey. It's perfect </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> for lounging around the house or pairing with jeans for a casual outing.           </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy, oversized turtleneck that I bought online. It's a   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> lovely shade of deep forest green, which complements my height and gives a         </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> flattering silhouette. The fabric is a soft wool blend that's warm without being   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> itchy, and it has ribbed cuffs and a ribbed hem that add a bit of texture and      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> detail. I love to pair it with leggings or skinny jeans and boots, and it's        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> perfect for those chilly days when I want to feel snug and stylish at the same     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> time.                                                                              </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a soft, worn-in gray shirt with a colorful floral design on </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the front. It's comfortable, and I love wearing it on casual days.                 </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a lovely soft cotton blend with a scoop neck. It's a        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> beautiful shade of lavender that complements my skin tone. The shirt has a         </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> delicate floral pattern around the neckline that adds a touch of femininity        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> without being too over the top. It's comfortable, fits perfectly, and has held up  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> wonderfully despite numerous washes. I always feel good wearing it, whether I'm    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> out for a casual lunch with friends or just relaxing at home.                      </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a cozy knit beanie with a pom-pom on top. It keeps me warm      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> during the winter months and adds a fun touch to my outfits.                       </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a lovely wide-brimmed sun hat that I found online a couple of   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> years ago. It's a soft beige color with a delicate ribbon around the base that     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> adds a touch of elegance. The brim is just wide enough to shield my eyes and face  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> from the sun without being cumbersome. It's made from a lightweight straw          </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> material, which makes it perfect for gardening or taking long walks in the park    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> during the summer months. It's both functional and stylish, and I always receive   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> compliments on it when I wear it out.                                              </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy cashmere pullover in a soft lavender color. It has a </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> relaxed fit and a cowl neck that keeps me warm during the chilly winter days.      </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy, chunky knit cardigan in a lovely shade of deep      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> blue. It has large buttons down the front and a shawl collar that keeps my neck    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> warm. The pockets are deep enough to keep my hands toasty or to hold my reading    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> glasses. I bought it online a couple of years ago, and it's been my go-to for      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> comfort ever since.                                                                </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a soft, gray V-neck with a cute floral design on the front. </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> It's so comfortable and goes with everything!                                      </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a soft, cotton blend with a classic fit. It's light blue    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> with a delicate floral pattern around the neckline. The sleeves are just the right </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> length, hitting at the mid-upper arm. It's one of those shirts that has aged well  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> over time, becoming even more comfortable with each wash. I bought it online a few </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> years back and it's been a staple in my wardrobe ever since. It's perfect for a    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> casual day out or just lounging around the house.                                  </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a wide-brimmed straw hat with a colorful floral band. It's      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> perfect for sunny days and adds a touch of style to any outfit.                    </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a cozy, knitted beanie that I found online a few years ago.     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> It's a lovely shade of teal with a cute, little pom-pom on top. Not only does it   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> keep my head warm during the chilly months, but it also adds a pop of color to my  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> outfits. I love that it's both stylish and functional.                             </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy, oversized knit in a deep burgundy color. It has a   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> cowl neck and long sleeves, perfect for chilly evenings by the fireplace.          </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy, oversized cable knit in a soft cream color. It has  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> a turtleneck that keeps me warm during the chillier months and long sleeves that I </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> can pull over my hands. The material is a blend of wool and cashmere, which makes  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> it incredibly soft to the touch and comfortable for long wear. I love pairing it   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> with leggings or jeans for a casual look, or dressing it up with a skirt and boots </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> if I'm going out. It's my go-to piece for comfort and style.                       </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a soft, light blue shirt with a vintage graphic design of a </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> beach sunset. It's comfortable and reminds me of relaxing vacations.               </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a classic, comfortable cotton blend with a scoop neck. It's </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> in a lovely shade of lavender that complements my skin tone nicely. The shirt has  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> a relaxed fit, which I prefer for my daily wear, and it features a small, elegant  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> embroidery of a hummingbird near the hem, which adds a touch of whimsy without     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> being too flashy. I found it on a specialty boutique's website a couple of years   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ago, and it's been a staple in my wardrobe ever since.                             </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a wide-brimmed straw hat with a colorful ribbon around it. It's </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> perfect for keeping the sun off my face during the summer months.                  </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a classic, wide-brimmed sun hat that I found online last        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> summer. It's made of a soft, lightweight straw material, perfect for keeping the   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sun off my face and neck during my garden work. The brim is just wide enough to    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> provide ample shade without being cumbersome. It has a lovely ribbon around the    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> base that adds a touch of elegance, and the neutral beige color goes well with     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> almost any outfit. It's both practical and stylish, and I love it!                 </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy, oversized knit in a deep burgundy color. It has a   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> cowl neck and long sleeves, perfect for staying warm on chilly days.               </span>│
    ├───────┼─────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy, oversized turtleneck that I found online last       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> winter. It's a lovely shade of deep forest green, which complements my eyes, and   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> it's made from a soft, wool-alpaca blend that keeps me warm without being itchy.   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> The sleeves are long enough to cover my hands, which I appreciate given my height, </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> and it has a ribbed texture that adds a touch of elegance. I love to pair it with  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> leggings and boots for a comfortable yet put-together look.                        </span>│
    └───────┴─────────┴──────────┴────────────────────────────────────────────────────────────────────────────────────┘
    </pre>



Filtering results
~~~~~~~~~~~~~~~~~

We can filter our responses by adding a logical expression to the
``filter`` method. Here we filter results to those provided by GPT-4
where the response to question ``q_nu`` is greater than 1000, and then
examine the response and ``_comment`` to question ``q_li`` together with
the response to ``q_nu``. We include the ``agent_name`` to show the
names that were generated for the agents as we did not specify them in
creating the agents:

.. code:: python

    (results_shopping
    .filter("q_nu > str(1000) and model.model == 'gpt-4-1106-preview'")
    .select("agent_name", "answer.q_nu", "answer.q_li", "answer.q_li_comment")
    .print()
    )



.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> agent       </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answer </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answer                                     </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answer                                      </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .agent_name </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_nu  </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_li                                      </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .q_li_comment                               </span>┃
    ┡━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Agent_0     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 500    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ['virtual fitting rooms', 'comprehensive   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> As someone who prefers to shop online, I    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> size charts', 'user reviews with photos',  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> find these features would greatly enhance   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> '360-degree product views', 'better filter </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the shopping experience, making it easier   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> options', 'personalized recommendations',  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> to choose the right items and reduce the    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'easy return policies', 'sustainable       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> need for returns.                           </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> fashion options']                          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                             </span>│
    ├─────────────┼────────┼────────────────────────────────────────────┼─────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Agent_1     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 500    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ['virtual fitting rooms', 'more size       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> These improvements would enhance the online </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> inclusivity', '360-degree product views',  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> shopping experience by providing a better   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'better fabric descriptions',              </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> understanding of how clothes might fit,     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'user-friendly mobile interface',          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> feel, and look in real life, which is often </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'sustainable fashion options', 'easy       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> a challenge when shopping online.           </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> return policies', 'detailed size charts',  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                             </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'customer reviews with photos', 'AI style  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                             </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> recommendations']                          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                             </span>│
    ├─────────────┼────────┼────────────────────────────────────────────┼─────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Agent_2     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 1200   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ['better size filters', 'virtual fitting   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> As someone who shops online frequently,     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> rooms', '360-degree views', 'detailed      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> I've noticed that these improvements could  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> fabric information', 'user reviews with    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> significantly enhance the shopping          </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> photos', 'flexible return policies',       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> experience by providing a better            </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'sustainable fashion options',             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> understanding of how clothes will fit,      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'inclusivity in sizing']                   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> feel, and look in real life.                </span>│
    ├─────────────┼────────┼────────────────────────────────────────────┼─────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Agent_3     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 500    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ['Better size filters', '360-degree        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> As an avid online shopper, I find these     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> product views', 'Virtual try-on',          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> features would greatly enhance the shopping </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'Detailed size guides', 'User reviews with </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> experience, reduce the likelihood of        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> photos', 'More inclusive size ranges']     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> returns, and help in making more informed   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> decisions.                                  </span>│
    ├─────────────┼────────┼────────────────────────────────────────────┼─────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Agent_4     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 500    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ['more size inclusivity', 'virtual fitting </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> As someone who shops online frequently, I'd </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> rooms', 'detailed sizing charts', 'user    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> love to see these improvements to enhance   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> reviews with photos', 'easy returns',      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the shopping experience and ensure a better </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'sustainable options', '360-degree product </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> fit for the clothes I buy.                  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> views', 'better search filters', 'live     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                             </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> chat support']                             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                             </span>│
    ├─────────────┼────────┼────────────────────────────────────────────┼─────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Agent_5     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 500    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ['virtual fitting rooms', 'better size     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> As a tall woman, finding clothes that fit   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> standardization', 'advanced search         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> well can be a challenge, especially online. </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> filters', '360-degree product views',      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> I'd love to see improvements that help      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'detailed fabric information',             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> simulate the in-store experience and        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'user-friendly mobile interface',          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> provide more information to make informed   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'augmented reality features',              </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> purchases.                                  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'personalized recommendations', 'easy      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                             </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> return process', 'sustainable options']    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                             </span>│
    ├─────────────┼────────┼────────────────────────────────────────────┼─────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Agent_6     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 300    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ['petite sections', '360-degree views',    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> As a short woman, I find it challenging to  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'virtual fitting rooms', 'detailed size    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> gauge how clothes will fit when shopping    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> charts', 'customer reviews with photos',   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> online. I'd love to see more options        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'easy return policies', 'filter by body    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tailored to petite frames, and tools like   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> type', 'more models of different sizes',   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> virtual fitting rooms would be incredibly   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'live chat support', 'loyalty discounts']  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> helpful. Detailed size charts and customer  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> reviews that include photos can also        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> provide a better sense of how an item might </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> fit. Easy return policies are essential     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> since things might not always work out. I   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> also appreciate being able to filter        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> clothes by body type and seeing them on     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> models who are more representative of my    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> size. Live chat support is great for any    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> questions, and who doesn't love a good      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> loyalty discount?                           </span>│
    ├─────────────┼────────┼────────────────────────────────────────────┼─────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Agent_7     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 500    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ['easier navigation', 'larger font sizes', </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> As an older shopper, I appreciate websites  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'more diverse models', 'virtual try-on',   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> that are easy to navigate with clear text   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'detailed size charts', 'customer reviews  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> and images. It's also helpful to see        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> with photos', 'accessible customer         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> clothes on models that represent a range of </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> service', 'filter by body shape',          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> body types, and virtual try-on features can </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> '360-degree product views']                </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> be a great way to get a better sense of how </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> something will fit. Detailed size charts    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> and customer reviews, especially with       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> photos, are invaluable for making informed  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> decisions. Lastly, having accessible        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> customer service and the ability to filter  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> clothes by body shape would greatly enhance </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the shopping experience.                    </span>│
    ├─────────────┼────────┼────────────────────────────────────────────┼─────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Agent_8     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 500    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ['more size options', 'user-friendly       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> As a tall woman, I often find it            </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> interfaces', 'virtual fitting rooms',      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> challenging to get the right fit when       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'detailed size charts', '360-degree        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> shopping online. I'd like to see more       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> product views', 'easy return policies',    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> inclusive sizing and better visualization   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'customer reviews with photos', 'filter by </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tools like virtual fitting rooms that could </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> body type', 'advanced search options',     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> help understand how clothes might fit.      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'live chat support']                       </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Detailed size charts specific to each       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> garment and the ability to see products     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> from multiple angles would also be          </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> beneficial. An easy return process is       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> crucial if something doesn't fit. Lastly,   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> having the option to see customer reviews   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> that include photos and filter clothes by   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> body type would help in making more         </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                            </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> informed decisions.                         </span>│
    └─────────────┴────────┴────────────────────────────────────────────┴─────────────────────────────────────────────┘
    </pre>



Table labels
~~~~~~~~~~~~

We can also apply some ``pretty_labels`` to our tables in the ``print``
method. Note that we do need to include the object prefixes in
specifying the labels in the print statement:

.. code:: python

    (results
    .select("age", "height","item", "favorite")
    .print(pretty_labels = {
        "agent.age": "Age",
        "agent.height": "Height",
        "scenario.item": "Item",
        "answer.favorite": q.question_text
    })
    )



.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━┳━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold">     </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold">         </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold">         </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> Describe your favorite {{ item }}                                                     </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> Age </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> Height  </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> Item    </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .                                                                                     </span>┃
    ┡━━━━━╇━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a cozy oversized black shirt with a cute graphic design on the </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> front. It's super comfortable and goes well with any pair of jeans or leggings.       </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a soft, heather gray cotton blend that fits just right, not    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> too tight or too loose. It has a quirky print of a cat sitting in a pocket on the     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> left chest area, which always seems to catch people's attention and make them smile.  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> I love that it's versatile enough to pair with jeans for a casual look or with a      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> blazer for a more put-together outfit. Plus, it's held up really well despite         </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> countless washes since I bought it online last year.                                  </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a cozy knit beanie with a faux fur pom-pom on top. It's perfect    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> for keeping me warm in the winter while adding a cute touch to my outfits.            </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a cozy, slouchy beanie that I found online last winter. It's a     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> beautiful shade of teal and made from a soft, chunky knit fabric that keeps my head   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> warm without being itchy. It has a cute, oversized pom-pom on top that adds a playful </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> touch to any outfit. I love that it's both stylish and functional, and it goes with   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> almost everything in my wardrobe.                                                     </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy, oversized knit in a soft pastel color. It's perfect    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> for lounging around the house or running errands on a chilly day.                     </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy, oversized knit that I found online last winter. It's a </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> lovely shade of heather gray, which makes it versatile enough to pair with almost     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> anything in my wardrobe. The material is super soft and warm, perfect for those       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> chilly days when I want to feel snug and comfortable. It has a relaxed fit, with a    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> slightly longer back that gives it a modern silhouette. The best part is the chunky   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> turtleneck that keeps the wind out and adds a stylish touch. I love curling up in it  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> with a good book or wearing it for a casual day out.                                  </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a soft, grey graphic tee with a cute design of a cat wearing   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sunglasses. It's super comfortable and goes well with jeans or leggings.              </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a soft, heather gray one with a relaxed fit. It has a          </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> vintage-looking print of a mountain range across the chest, which reminds me of my    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> love for the outdoors. The fabric is a cotton blend, which makes it really            </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> comfortable for everyday wear, and it's held up really well despite numerous washes.  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> I love that it pairs easily with jeans or shorts, and it's my go-to for a casual, yet </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> put-together look.                                                                    </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a cozy knit beanie in a neutral color that goes with everything.   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> It keeps me warm and stylish during the colder months.                                </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a cozy, oversized beanie that I found online last winter. It's a   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> soft, chunky knit in a beautiful shade of heather gray, which goes with almost        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> everything in my wardrobe. It has a slouchy fit that makes it look effortlessly       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> stylish, and it's warm enough to keep me comfortable on the chilliest days. I love    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> that it's versatile enough to wear with a casual outfit or to add a bit of laid-back  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> cool to something more dressed up.                                                    </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy oversized knit in a soft pastel pink color. It has a    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> turtleneck and long sleeves, perfect for keeping me warm during the colder months.    </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is this cozy, oversized knit that I found online last winter.     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> It's a soft shade of heather gray, which makes it really versatile and easy to pair   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> with almost anything in my wardrobe. The material is a blend of wool and cashmere, so </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> it's incredibly warm and just feels like a hug whenever I put it on. It has a chunky  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> turtleneck that keeps me snug on chilly days and the sleeves are long enough to cover </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> my hands, which I love. I also really like the ribbed cuffs and hem because they add  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> a bit of texture and detail. It's definitely my go-to piece for comfort and style     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> during the colder months.                                                             </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a soft, oversized white shirt with a vintage band logo on the  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> front. It's super comfortable and goes well with jeans or leggings.                   </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a heather gray, soft cotton blend with a relaxed fit that's    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> just perfect for casual days. It has a minimalistic design with a small, embroidered  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> cactus on the left chest area that adds a touch of whimsy. The sleeves are slightly   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> rolled up, giving it a cool, effortless vibe. It's my go-to piece for comfort and     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> style, and I love how it pairs with almost anything from jeans to skirts.             </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a wide-brimmed black fedora with a sleek design. It's perfect for  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> adding a touch of style to any outfit.                                                </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a wide-brimmed, floppy sun hat that I bought online. It's made     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> from a light, woven straw material, which makes it perfect for sunny days. The hat    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> has a black ribbon around the crown that adds a touch of elegance, and it's           </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> incredibly versatile – I can wear it to the beach or pair it with a cute summer dress </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> for an outdoor lunch. It's not only stylish but also functional, as it protects my    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> face from the sun while making a fashion statement.                                   </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy oversized knit in a soft gray color. It's perfect for   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> lounging around the house or running errands on chilly days.                          </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 25  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy, oversized turtleneck that comes in a soft shade of     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> heather grey. It's made from a blend of wool and cashmere, which makes it incredibly  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> warm and soft to the touch. The sleeves are long enough to cover my hands, which I    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> love, and the turtleneck part can be scrunched down or pulled up over my chin for     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> extra warmth. It has a ribbed texture that adds a bit of detail to its simple design, </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> and it's long enough to wear with leggings for a comfy, casual look. I found it       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> online last year and it's been my go-to ever since for chilly days.                   </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a soft, grey V-neck with a simple design of a coffee cup on    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the front. It's comfortable and goes with everything.                                 </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a classic, fitted black tee with a subtle, yet elegant, white  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> floral pattern that cascades down one shoulder. It's made from a soft, breathable     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> cotton blend that has just the right amount of stretch to be comfortable without      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> losing its shape. I love that it's versatile enough to wear with jeans for a casual   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> look or dressed up under a blazer for a more formal occasion. It's been a staple in   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> my wardrobe for years, and it's held up beautifully through countless washes. Plus,   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the length is just right for my short stature, hitting at the hip without             </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> overwhelming my frame.                                                                </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a cozy knit beanie in a dark grey color with a faux fur pom pom on </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> top. It keeps me warm and stylish during the colder months.                           </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a cozy, knit beanie that I found online last winter. It's a deep   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> burgundy color, which I love because it goes with almost everything in my wardrobe.   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> The beanie is made from a soft wool blend that keeps my head warm without being       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> itchy, and it has a cute, oversized pom-pom on top that adds a bit of fun to my       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> winter outfits. It's snug but stretches just enough to fit comfortably, and it        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> doesn't mess up my hair too much when I take it off. I always get compliments on it   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> whenever I wear it out.                                                               </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy, oversized knit in a soft shade of gray. It's perfect   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> for lounging around the house or running errands on chilly days.                      </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy, oversized turtleneck in a soft shade of heather gray.  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> It's made from a blend of wool and cashmere, which makes it incredibly warm and soft  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> against the skin. The sleeves are long enough to cover my hands, which I love, and it </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> has a chunky ribbed texture that adds a bit of visual interest without being too      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> loud. It's the kind of sweater that pairs well with leggings or skinny jeans, and I   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> can easily dress it up or down. It's my go-to piece for chilly days when I want to    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> feel snug and stylish at the same time.                                               </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a soft, grey V-neck with a cute graphic print of a coffee cup  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> on it. It's super comfy and goes well with jeans or leggings.                         </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a soft, heather gray one that fits just right – not too tight, </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> but not too loose either. It has a scoop neck that's flattering without being too     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> revealing, and the material is a breathable cotton blend that's comfortable for       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> all-day wear. The front has a subtle, vintage-style graphic of a mountain range with  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the words 'Explore More' written underneath, which always reminds me of my love for   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the outdoors and adventure. I've had it for years, and it's held up really well       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> despite countless washes. It's definitely my go-to tee for casual days or when I'm    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> running errands.                                                                      </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a cozy knit beanie with a faux fur pom-pom on top. It keeps me     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> warm during the winter months and adds a touch of fun to my outfits.                  </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a cozy, chunky knit beanie that I found online last winter. It's a </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> lovely shade of deep blue that matches well with most of my wardrobe, and it has a    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> cute, oversized pom-pom on top. It's both stylish and functional, keeping my head     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> warm during the chilly months. I love that it's made from soft, high-quality yarn,    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> which doesn't itch or irritate my skin. I've received several compliments on it and   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> it's my go-to accessory for cold days.                                                </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy, oversized knit in a beautiful shade of deep burgundy.  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> It's perfect for lounging around the house or pairing with jeans for a casual day     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> out.                                                                                  </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy, oversized cable knit in a soft cream color. It has a   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> chunky turtleneck that keeps me warm during chilly days and long sleeves that I can   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> pull over my hands. It's made from a blend of wool and cashmere, which makes it       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> incredibly soft to the touch and comfortable for all-day wear. I love pairing it with </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> leggings or skinny jeans and boots for a casual, yet put-together look.               </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a soft, gray V-neck with a subtle floral pattern. It's         </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> comfortable and versatile, perfect for lounging at home or running errands.           </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a soft, vintage-style charcoal gray one that has a classic     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> rock band's logo on the front. It's slightly oversized, which makes it perfect for a  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> relaxed look, and the cotton material has worn in so well over the years that it      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> feels like a second skin. I love pairing it with jeans and sneakers for a casual day  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> out or lounging at home. It's my go-to piece for comfort and a touch of nostalgia.    </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a wide-brimmed straw hat that I bought online. It's perfect for    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sunny days and adds a touch of style to any outfit.                                   </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a sleek, wide-brimmed fedora that I found on a boutique website a  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> few years ago. It's a beautiful shade of navy blue that seems to go with everything,  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> and the material is a soft, felted wool that feels luxurious to the touch. It has a   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> subtle, leather band around the base of the crown that adds just the right amount of  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> detail without being too flashy. It's my go-to for sunny days or when I want to add a </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> touch of elegance to my outfit.                                                       </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy oversized knit in a soft shade of grey. It's perfect    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> for lounging around the house or pairing with jeans for a casual outing.              </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 45  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy, oversized turtleneck that I bought online. It's a      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> lovely shade of deep forest green, which complements my height and gives a flattering </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> silhouette. The fabric is a soft wool blend that's warm without being itchy, and it   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> has ribbed cuffs and a ribbed hem that add a bit of texture and detail. I love to     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> pair it with leggings or skinny jeans and boots, and it's perfect for those chilly    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> days when I want to feel snug and stylish at the same time.                           </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a soft, worn-in gray shirt with a colorful floral design on    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the front. It's comfortable, and I love wearing it on casual days.                    </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a lovely soft cotton blend with a scoop neck. It's a beautiful </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> shade of lavender that complements my skin tone. The shirt has a delicate floral      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> pattern around the neckline that adds a touch of femininity without being too over    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the top. It's comfortable, fits perfectly, and has held up wonderfully despite        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> numerous washes. I always feel good wearing it, whether I'm out for a casual lunch    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> with friends or just relaxing at home.                                                </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a cozy knit beanie with a pom-pom on top. It keeps me warm during  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> the winter months and adds a fun touch to my outfits.                                 </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a lovely wide-brimmed sun hat that I found online a couple of      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> years ago. It's a soft beige color with a delicate ribbon around the base that adds a </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> touch of elegance. The brim is just wide enough to shield my eyes and face from the   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sun without being cumbersome. It's made from a lightweight straw material, which      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> makes it perfect for gardening or taking long walks in the park during the summer     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> months. It's both functional and stylish, and I always receive compliments on it when </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> I wear it out.                                                                        </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy cashmere pullover in a soft lavender color. It has a    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> relaxed fit and a cowl neck that keeps me warm during the chilly winter days.         </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> short   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy, chunky knit cardigan in a lovely shade of deep blue.   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> It has large buttons down the front and a shawl collar that keeps my neck warm. The   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> pockets are deep enough to keep my hands toasty or to hold my reading glasses. I      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> bought it online a couple of years ago, and it's been my go-to for comfort ever       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> since.                                                                                </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a soft, gray V-neck with a cute floral design on the front.    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> It's so comfortable and goes with everything!                                         </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a soft, cotton blend with a classic fit. It's light blue with  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> a delicate floral pattern around the neckline. The sleeves are just the right length, </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hitting at the mid-upper arm. It's one of those shirts that has aged well over time,  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> becoming even more comfortable with each wash. I bought it online a few years back    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> and it's been a staple in my wardrobe ever since. It's perfect for a casual day out   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> or just lounging around the house.                                                    </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a wide-brimmed straw hat with a colorful floral band. It's perfect </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> for sunny days and adds a touch of style to any outfit.                               </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a cozy, knitted beanie that I found online a few years ago. It's a </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> lovely shade of teal with a cute, little pom-pom on top. Not only does it keep my     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> head warm during the chilly months, but it also adds a pop of color to my outfits. I  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> love that it's both stylish and functional.                                           </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy, oversized knit in a deep burgundy color. It has a cowl </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> neck and long sleeves, perfect for chilly evenings by the fireplace.                  </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> average </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy, oversized cable knit in a soft cream color. It has a   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> turtleneck that keeps me warm during the chillier months and long sleeves that I can  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> pull over my hands. The material is a blend of wool and cashmere, which makes it      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> incredibly soft to the touch and comfortable for long wear. I love pairing it with    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> leggings or jeans for a casual look, or dressing it up with a skirt and boots if I'm  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> going out. It's my go-to piece for comfort and style.                                 </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a soft, light blue shirt with a vintage graphic design of a    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> beach sunset. It's comfortable and reminds me of relaxing vacations.                  </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite t-shirt is a classic, comfortable cotton blend with a scoop neck. It's in </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> a lovely shade of lavender that complements my skin tone nicely. The shirt has a      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> relaxed fit, which I prefer for my daily wear, and it features a small, elegant       </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> embroidery of a hummingbird near the hem, which adds a touch of whimsy without being  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> too flashy. I found it on a specialty boutique's website a couple of years ago, and   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> it's been a staple in my wardrobe ever since.                                         </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a wide-brimmed straw hat with a colorful ribbon around it. It's    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> perfect for keeping the sun off my face during the summer months.                     </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite hat is a classic, wide-brimmed sun hat that I found online last summer.   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> It's made of a soft, lightweight straw material, perfect for keeping the sun off my   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> face and neck during my garden work. The brim is just wide enough to provide ample    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> shade without being cumbersome. It has a lovely ribbon around the base that adds a    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> touch of elegance, and the neutral beige color goes well with almost any outfit. It's </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> both practical and stylish, and I love it!                                            </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy, oversized knit in a deep burgundy color. It has a cowl </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> neck and long sleeves, perfect for staying warm on chilly days.                       </span>│
    ├─────┼─────────┼─────────┼───────────────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 65  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> tall    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite sweater is a cozy, oversized turtleneck that I found online last winter.  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> It's a lovely shade of deep forest green, which complements my eyes, and it's made    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> from a soft, wool-alpaca blend that keeps me warm without being itchy. The sleeves    </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> are long enough to cover my hands, which I appreciate given my height, and it has a   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> ribbed texture that adds a touch of elegance. I love to pair it with leggings and     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">     </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">         </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> boots for a comfortable yet put-together look.                                        </span>│
    └─────┴─────────┴─────────┴───────────────────────────────────────────────────────────────────────────────────────┘
    </pre>



Prompts
~~~~~~~

We can examine the default prompts for each question type by selecting
them in the results. The following command will print both the system
and user prompts for each question in the results. For convenience, we
filter results to a single agent and model:

.. code:: python

    (results
    .filter("agent_name == 'Agent_0' and model.model == 'gpt-4-1106-preview'")
    .select("item", "prompt.*")
    .print()
    )



.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> scenario </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> prompt                                            </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> prompt                                           </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .item    </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .favorite_system_prompt                           </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .favorite_user_prompt                            </span>┃
    ┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'text': "You are answering questions as if you   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'text': 'You are being asked the following      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> were a human. Do not break character. You are an  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> question: Describe your favorite                 </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> agent with the following persona:\n{'persona':    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> t-shirt.\nReturn a valid JSON formatted like     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'You are a 25-year-old short woman who prefers to </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> this:\n{"answer": "&lt;put free text answer         </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> shop online.', 'age': 25, 'height': 'short'}",    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> here&gt;"}', 'class_name': 'FreeText'}              </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'class_name': 'AgentInstruction'}                 </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                                  </span>│
    ├──────────┼───────────────────────────────────────────────────┼──────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> hat      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'text': "You are answering questions as if you   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'text': 'You are being asked the following      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> were a human. Do not break character. You are an  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> question: Describe your favorite hat.\nReturn a  </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> agent with the following persona:\n{'persona':    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> valid JSON formatted like this:\n{"answer":      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'You are a 25-year-old short woman who prefers to </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> "&lt;put free text answer here&gt;"}', 'class_name':   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> shop online.', 'age': 25, 'height': 'short'}",    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'FreeText'}                                      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'class_name': 'AgentInstruction'}                 </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                                  </span>│
    ├──────────┼───────────────────────────────────────────────────┼──────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'text': "You are answering questions as if you   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> {'text': 'You are being asked the following      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> were a human. Do not break character. You are an  </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> question: Describe your favorite                 </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> agent with the following persona:\n{'persona':    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> sweater.\nReturn a valid JSON formatted like     </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'You are a 25-year-old short woman who prefers to </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> this:\n{"answer": "&lt;put free text answer         </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> shop online.', 'age': 25, 'height': 'short'}",    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> here&gt;"}', 'class_name': 'FreeText'}              </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">          </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> 'class_name': 'AgentInstruction'}                 </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                                                  </span>│
    └──────────┴───────────────────────────────────────────────────┴──────────────────────────────────────────────────┘
    </pre>



Analysis & visualization
~~~~~~~~~~~~~~~~~~~~~~~~

The EDSL libary has a variety of methods for analyzing and visualizing
results.

Dataframes
^^^^^^^^^^

Results objects can be converted to pandas dataframes with the
``to_pandas`` method:

.. code:: python

    results.to_pandas()




.. raw:: html

    <div>
    <style scoped>
        .dataframe tbody tr th:only-of-type {
            vertical-align: middle;
        }
    
        .dataframe tbody tr th {
            vertical-align: top;
        }
    
        .dataframe thead th {
            text-align: right;
        }
    </style>
    <table border="1" class="dataframe">
      <thead>
        <tr style="text-align: right;">
          <th></th>
          <th>agent.age</th>
          <th>agent.agent_name</th>
          <th>agent.height</th>
          <th>agent.persona</th>
          <th>answer.favorite</th>
          <th>model.frequency_penalty</th>
          <th>model.max_tokens</th>
          <th>model.model</th>
          <th>model.presence_penalty</th>
          <th>model.temperature</th>
          <th>model.top_p</th>
          <th>model.use_cache</th>
          <th>prompt.favorite_system_prompt</th>
          <th>prompt.favorite_user_prompt</th>
          <th>raw_model_response.favorite_raw_model_response</th>
          <th>scenario.item</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th>0</th>
          <td>25</td>
          <td>Agent_0</td>
          <td>short</td>
          <td>You are a 25-year-old short woman who prefers ...</td>
          <td>My favorite t-shirt is a cozy oversized black ...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAHnZrytxfxyVVHh0FqWqefVdc...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>1</th>
          <td>25</td>
          <td>Agent_0</td>
          <td>short</td>
          <td>You are a 25-year-old short woman who prefers ...</td>
          <td>My favorite t-shirt is a soft, heather gray co...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmuBG3mjE2dNqvkm0NviMfGwkI0...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>2</th>
          <td>25</td>
          <td>Agent_0</td>
          <td>short</td>
          <td>You are a 25-year-old short woman who prefers ...</td>
          <td>My favorite hat is a cozy knit beanie with a f...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAHnqtmkuke56NB8iNPZKfPMY4...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>3</th>
          <td>25</td>
          <td>Agent_0</td>
          <td>short</td>
          <td>You are a 25-year-old short woman who prefers ...</td>
          <td>My favorite hat is a cozy, slouchy beanie that...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmtJlO5LIcJV5SZjX9QG3ODQtvh...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>4</th>
          <td>25</td>
          <td>Agent_0</td>
          <td>short</td>
          <td>You are a 25-year-old short woman who prefers ...</td>
          <td>My favorite sweater is a cozy, oversized knit ...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAw1JDq0PsWmgxVgAPq9vaPr3Z...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>5</th>
          <td>25</td>
          <td>Agent_0</td>
          <td>short</td>
          <td>You are a 25-year-old short woman who prefers ...</td>
          <td>My favorite sweater is a cozy, oversized knit ...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmuda7sr7yKp0WS9NNuZAAV4YMx...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>6</th>
          <td>25</td>
          <td>Agent_1</td>
          <td>average</td>
          <td>You are a 25-year-old average woman who prefer...</td>
          <td>My favorite t-shirt is a soft, grey graphic te...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmBxPK9IYgVuiYciL4tnw1oKdIv...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>7</th>
          <td>25</td>
          <td>Agent_1</td>
          <td>average</td>
          <td>You are a 25-year-old average woman who prefer...</td>
          <td>My favorite t-shirt is a soft, heather gray on...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmuJYaoObbYPR0JNlN1aiftXf13...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>8</th>
          <td>25</td>
          <td>Agent_1</td>
          <td>average</td>
          <td>You are a 25-year-old average woman who prefer...</td>
          <td>My favorite hat is a cozy knit beanie in a neu...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmALfqa6ce5iYzlfehxfOtZif3u...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>9</th>
          <td>25</td>
          <td>Agent_1</td>
          <td>average</td>
          <td>You are a 25-year-old average woman who prefer...</td>
          <td>My favorite hat is a cozy, oversized beanie th...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmtrJUFsJLGjM3YChve5K109xa9...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>10</th>
          <td>25</td>
          <td>Agent_1</td>
          <td>average</td>
          <td>You are a 25-year-old average woman who prefer...</td>
          <td>My favorite sweater is a cozy oversized knit i...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAmkBWVIg9BvTYzmfoFWXEX8Sl...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>11</th>
          <td>25</td>
          <td>Agent_1</td>
          <td>average</td>
          <td>You are a 25-year-old average woman who prefer...</td>
          <td>My favorite sweater is this cozy, oversized kn...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmuOxMTluNfV3qz9cL1X2XW3JQ3...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>12</th>
          <td>25</td>
          <td>Agent_2</td>
          <td>tall</td>
          <td>You are a 25-year-old tall woman who prefers t...</td>
          <td>My favorite t-shirt is a soft, oversized white...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAoccKU47K64FjhSs5iME5LBvG...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>13</th>
          <td>25</td>
          <td>Agent_2</td>
          <td>tall</td>
          <td>You are a 25-year-old tall woman who prefers t...</td>
          <td>My favorite t-shirt is a heather gray, soft co...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmtaNdRgVUx3AgmCPxzTsxQmm1Y...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>14</th>
          <td>25</td>
          <td>Agent_2</td>
          <td>tall</td>
          <td>You are a 25-year-old tall woman who prefers t...</td>
          <td>My favorite hat is a wide-brimmed black fedora...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmB4mHAiCgjF0VUkdLlbB4niWHN...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>15</th>
          <td>25</td>
          <td>Agent_2</td>
          <td>tall</td>
          <td>You are a 25-year-old tall woman who prefers t...</td>
          <td>My favorite hat is a wide-brimmed, floppy sun ...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmuYjcqiJjPc2OnrQb1PHjLFpfK...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>16</th>
          <td>25</td>
          <td>Agent_2</td>
          <td>tall</td>
          <td>You are a 25-year-old tall woman who prefers t...</td>
          <td>My favorite sweater is a cozy oversized knit i...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAiV7LLJy4oAJSwVU2gUcwbkW7...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>17</th>
          <td>25</td>
          <td>Agent_2</td>
          <td>tall</td>
          <td>You are a 25-year-old tall woman who prefers t...</td>
          <td>My favorite sweater is a cozy, oversized turtl...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmudG3DlMX60phP4xBsicVyCLkf...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>18</th>
          <td>45</td>
          <td>Agent_3</td>
          <td>short</td>
          <td>You are a 45-year-old short woman who prefers ...</td>
          <td>My favorite t-shirt is a soft, grey V-neck wit...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAVGeNKF5InLUKrB4RVt9URzqj...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>19</th>
          <td>45</td>
          <td>Agent_3</td>
          <td>short</td>
          <td>You are a 45-year-old short woman who prefers ...</td>
          <td>My favorite t-shirt is a classic, fitted black...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmtONenP8w2It4LUeYhh2oZqxlJ...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>20</th>
          <td>45</td>
          <td>Agent_3</td>
          <td>short</td>
          <td>You are a 45-year-old short woman who prefers ...</td>
          <td>My favorite hat is a cozy knit beanie in a dar...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmA5MmHTeWnkQVI42vT3IAlVpcs...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>21</th>
          <td>45</td>
          <td>Agent_3</td>
          <td>short</td>
          <td>You are a 45-year-old short woman who prefers ...</td>
          <td>My favorite hat is a cozy, knit beanie that I ...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmucl3Xr80F5zV1kts5o14a8OXW...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>22</th>
          <td>45</td>
          <td>Agent_3</td>
          <td>short</td>
          <td>You are a 45-year-old short woman who prefers ...</td>
          <td>My favorite sweater is a cozy, oversized knit ...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAhQovb0WGc3ftUdj5LOh1M3K7...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>23</th>
          <td>45</td>
          <td>Agent_3</td>
          <td>short</td>
          <td>You are a 45-year-old short woman who prefers ...</td>
          <td>My favorite sweater is a cozy, oversized turtl...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmugDO6bl5uXGP7brPPF2MKIuXn...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>24</th>
          <td>45</td>
          <td>Agent_4</td>
          <td>average</td>
          <td>You are a 45-year-old average woman who prefer...</td>
          <td>My favorite t-shirt is a soft, grey V-neck wit...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAaGJoQ6MGbz49FSAgP8JplWvw...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>25</th>
          <td>45</td>
          <td>Agent_4</td>
          <td>average</td>
          <td>You are a 45-year-old average woman who prefer...</td>
          <td>My favorite t-shirt is a soft, heather gray on...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmt05MAS2e7tBBk5I6FqAJF132C...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>26</th>
          <td>45</td>
          <td>Agent_4</td>
          <td>average</td>
          <td>You are a 45-year-old average woman who prefer...</td>
          <td>My favorite hat is a cozy knit beanie with a f...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAEXXlsbjP0b4wozpb5xjVrjF7...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>27</th>
          <td>45</td>
          <td>Agent_4</td>
          <td>average</td>
          <td>You are a 45-year-old average woman who prefer...</td>
          <td>My favorite hat is a cozy, chunky knit beanie ...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmujWuEo2TKV6pxqLV7NQE3jdYC...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>28</th>
          <td>45</td>
          <td>Agent_4</td>
          <td>average</td>
          <td>You are a 45-year-old average woman who prefer...</td>
          <td>My favorite sweater is a cozy, oversized knit ...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmBY6qOiWVMT9ejak6Neceho9ZV...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>29</th>
          <td>45</td>
          <td>Agent_4</td>
          <td>average</td>
          <td>You are a 45-year-old average woman who prefer...</td>
          <td>My favorite sweater is a cozy, oversized cable...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmtNGySJkQepUtOYJyO24Dfct6L...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>30</th>
          <td>45</td>
          <td>Agent_5</td>
          <td>tall</td>
          <td>You are a 45-year-old tall woman who prefers t...</td>
          <td>My favorite t-shirt is a soft, gray V-neck wit...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmApg3WMmsxhHGCQvYoQmbRNnKk...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>31</th>
          <td>45</td>
          <td>Agent_5</td>
          <td>tall</td>
          <td>You are a 45-year-old tall woman who prefers t...</td>
          <td>My favorite t-shirt is a soft, vintage-style c...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmtMaqKc9XqSAUFG2qfUkxhFfk1...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>32</th>
          <td>45</td>
          <td>Agent_5</td>
          <td>tall</td>
          <td>You are a 45-year-old tall woman who prefers t...</td>
          <td>My favorite hat is a wide-brimmed straw hat th...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAuZ0wrUje85kIa5B2K44XP1LZ...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>33</th>
          <td>45</td>
          <td>Agent_5</td>
          <td>tall</td>
          <td>You are a 45-year-old tall woman who prefers t...</td>
          <td>My favorite hat is a sleek, wide-brimmed fedor...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmtq3KX9z5836h0LDpufFqrmjIx...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>34</th>
          <td>45</td>
          <td>Agent_5</td>
          <td>tall</td>
          <td>You are a 45-year-old tall woman who prefers t...</td>
          <td>My favorite sweater is a cozy oversized knit i...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmA7kRJIZF5FchRN8qpWBfpKGRB...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>35</th>
          <td>45</td>
          <td>Agent_5</td>
          <td>tall</td>
          <td>You are a 45-year-old tall woman who prefers t...</td>
          <td>My favorite sweater is a cozy, oversized turtl...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmulpAMtw7dSA4x4NwEqcJq4mIR...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>36</th>
          <td>65</td>
          <td>Agent_6</td>
          <td>short</td>
          <td>You are a 65-year-old short woman who prefers ...</td>
          <td>My favorite t-shirt is a soft, worn-in gray sh...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmA4OEhBOXzsR31tFEZbT4jgwnG...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>37</th>
          <td>65</td>
          <td>Agent_6</td>
          <td>short</td>
          <td>You are a 65-year-old short woman who prefers ...</td>
          <td>My favorite t-shirt is a lovely soft cotton bl...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmtQ7kQGIX0dvGB2PgPABGF2VE3...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>38</th>
          <td>65</td>
          <td>Agent_6</td>
          <td>short</td>
          <td>You are a 65-year-old short woman who prefers ...</td>
          <td>My favorite hat is a cozy knit beanie with a p...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmBQGnyGFk9a23BfXxEEe5lLmdU...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>39</th>
          <td>65</td>
          <td>Agent_6</td>
          <td>short</td>
          <td>You are a 65-year-old short woman who prefers ...</td>
          <td>My favorite hat is a lovely wide-brimmed sun h...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmuzSiApQnWkSgMkUjJP1pytqIg...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>40</th>
          <td>65</td>
          <td>Agent_6</td>
          <td>short</td>
          <td>You are a 65-year-old short woman who prefers ...</td>
          <td>My favorite sweater is a cozy cashmere pullove...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAu0AlDDAurrWPVF0vRsgKnOtL...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>41</th>
          <td>65</td>
          <td>Agent_6</td>
          <td>short</td>
          <td>You are a 65-year-old short woman who prefers ...</td>
          <td>My favorite sweater is a cozy, chunky knit car...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmua52DRGjxXvd9B6htIvdl24Ao...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>42</th>
          <td>65</td>
          <td>Agent_7</td>
          <td>average</td>
          <td>You are a 65-year-old average woman who prefer...</td>
          <td>My favorite t-shirt is a soft, gray V-neck wit...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAT4s8HP5R0gkHcznkCgBOdJbm...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>43</th>
          <td>65</td>
          <td>Agent_7</td>
          <td>average</td>
          <td>You are a 65-year-old average woman who prefer...</td>
          <td>My favorite t-shirt is a soft, cotton blend wi...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmuDomfWWiDCQvO6nDfjdiPnUtV...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>44</th>
          <td>65</td>
          <td>Agent_7</td>
          <td>average</td>
          <td>You are a 65-year-old average woman who prefer...</td>
          <td>My favorite hat is a wide-brimmed straw hat wi...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAfzuUYbXZNy0slRaFEi4xQp5o...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>45</th>
          <td>65</td>
          <td>Agent_7</td>
          <td>average</td>
          <td>You are a 65-year-old average woman who prefer...</td>
          <td>My favorite hat is a cozy, knitted beanie that...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmtZIFugmxx4aC2rl9j8WhIUt1e...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>46</th>
          <td>65</td>
          <td>Agent_7</td>
          <td>average</td>
          <td>You are a 65-year-old average woman who prefer...</td>
          <td>My favorite sweater is a cozy, oversized knit ...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAxZXdQl9KUJrGLmKcBjIH3z0T...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>47</th>
          <td>65</td>
          <td>Agent_7</td>
          <td>average</td>
          <td>You are a 65-year-old average woman who prefer...</td>
          <td>My favorite sweater is a cozy, oversized cable...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmtjDfsCynQDFQodo3jcFDHXgCp...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>48</th>
          <td>65</td>
          <td>Agent_8</td>
          <td>tall</td>
          <td>You are a 65-year-old tall woman who prefers t...</td>
          <td>My favorite t-shirt is a soft, light blue shir...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAC1xvYUF73C3IjNUyBXAtwUuL...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>49</th>
          <td>65</td>
          <td>Agent_8</td>
          <td>tall</td>
          <td>You are a 65-year-old tall woman who prefers t...</td>
          <td>My favorite t-shirt is a classic, comfortable ...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmuBMVGdYxOBROTfdypkHDgoS2N...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>50</th>
          <td>65</td>
          <td>Agent_8</td>
          <td>tall</td>
          <td>You are a 65-year-old tall woman who prefers t...</td>
          <td>My favorite hat is a wide-brimmed straw hat wi...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAwc7Zej4A8bcHnrsMI5EYMvbv...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>51</th>
          <td>65</td>
          <td>Agent_8</td>
          <td>tall</td>
          <td>You are a 65-year-old tall woman who prefers t...</td>
          <td>My favorite hat is a classic, wide-brimmed sun...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmuU5KKnWvQmseY4HsSQ8i5nH4w...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>52</th>
          <td>65</td>
          <td>Agent_8</td>
          <td>tall</td>
          <td>You are a 65-year-old tall woman who prefers t...</td>
          <td>My favorite sweater is a cozy, oversized knit ...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAVC7xkd5ChqUOIpGHD7uMeSqu...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>53</th>
          <td>65</td>
          <td>Agent_8</td>
          <td>tall</td>
          <td>You are a 65-year-old tall woman who prefers t...</td>
          <td>My favorite sweater is a cozy, oversized turtl...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>True</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmuxHMtxQ8KDTS6gegyQ8F97PzM...</td>
          <td>sweater</td>
        </tr>
      </tbody>
    </table>
    </div>



SQL
^^^

Results objects support SQL queries with the ``sql`` method.:

.. code:: python

    results.sql("select * from self", shape="wide")




.. raw:: html

    <div>
    <style scoped>
        .dataframe tbody tr th:only-of-type {
            vertical-align: middle;
        }
    
        .dataframe tbody tr th {
            vertical-align: top;
        }
    
        .dataframe thead th {
            text-align: right;
        }
    </style>
    <table border="1" class="dataframe">
      <thead>
        <tr style="text-align: right;">
          <th></th>
          <th>agent.age</th>
          <th>agent.agent_name</th>
          <th>agent.height</th>
          <th>agent.persona</th>
          <th>answer.favorite</th>
          <th>model.frequency_penalty</th>
          <th>model.max_tokens</th>
          <th>model.model</th>
          <th>model.presence_penalty</th>
          <th>model.temperature</th>
          <th>model.top_p</th>
          <th>model.use_cache</th>
          <th>prompt.favorite_system_prompt</th>
          <th>prompt.favorite_user_prompt</th>
          <th>raw_model_response.favorite_raw_model_response</th>
          <th>scenario.item</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th>0</th>
          <td>25</td>
          <td>Agent_0</td>
          <td>short</td>
          <td>You are a 25-year-old short woman who prefers ...</td>
          <td>My favorite t-shirt is a cozy oversized black ...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAHnZrytxfxyVVHh0FqWqefVdc...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>1</th>
          <td>25</td>
          <td>Agent_0</td>
          <td>short</td>
          <td>You are a 25-year-old short woman who prefers ...</td>
          <td>My favorite t-shirt is a soft, heather gray co...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmuBG3mjE2dNqvkm0NviMfGwkI0...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>2</th>
          <td>25</td>
          <td>Agent_0</td>
          <td>short</td>
          <td>You are a 25-year-old short woman who prefers ...</td>
          <td>My favorite hat is a cozy knit beanie with a f...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAHnqtmkuke56NB8iNPZKfPMY4...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>3</th>
          <td>25</td>
          <td>Agent_0</td>
          <td>short</td>
          <td>You are a 25-year-old short woman who prefers ...</td>
          <td>My favorite hat is a cozy, slouchy beanie that...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmtJlO5LIcJV5SZjX9QG3ODQtvh...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>4</th>
          <td>25</td>
          <td>Agent_0</td>
          <td>short</td>
          <td>You are a 25-year-old short woman who prefers ...</td>
          <td>My favorite sweater is a cozy, oversized knit ...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAw1JDq0PsWmgxVgAPq9vaPr3Z...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>5</th>
          <td>25</td>
          <td>Agent_0</td>
          <td>short</td>
          <td>You are a 25-year-old short woman who prefers ...</td>
          <td>My favorite sweater is a cozy, oversized knit ...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmuda7sr7yKp0WS9NNuZAAV4YMx...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>6</th>
          <td>25</td>
          <td>Agent_1</td>
          <td>average</td>
          <td>You are a 25-year-old average woman who prefer...</td>
          <td>My favorite t-shirt is a soft, grey graphic te...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmBxPK9IYgVuiYciL4tnw1oKdIv...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>7</th>
          <td>25</td>
          <td>Agent_1</td>
          <td>average</td>
          <td>You are a 25-year-old average woman who prefer...</td>
          <td>My favorite t-shirt is a soft, heather gray on...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmuJYaoObbYPR0JNlN1aiftXf13...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>8</th>
          <td>25</td>
          <td>Agent_1</td>
          <td>average</td>
          <td>You are a 25-year-old average woman who prefer...</td>
          <td>My favorite hat is a cozy knit beanie in a neu...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmALfqa6ce5iYzlfehxfOtZif3u...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>9</th>
          <td>25</td>
          <td>Agent_1</td>
          <td>average</td>
          <td>You are a 25-year-old average woman who prefer...</td>
          <td>My favorite hat is a cozy, oversized beanie th...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmtrJUFsJLGjM3YChve5K109xa9...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>10</th>
          <td>25</td>
          <td>Agent_1</td>
          <td>average</td>
          <td>You are a 25-year-old average woman who prefer...</td>
          <td>My favorite sweater is a cozy oversized knit i...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAmkBWVIg9BvTYzmfoFWXEX8Sl...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>11</th>
          <td>25</td>
          <td>Agent_1</td>
          <td>average</td>
          <td>You are a 25-year-old average woman who prefer...</td>
          <td>My favorite sweater is this cozy, oversized kn...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmuOxMTluNfV3qz9cL1X2XW3JQ3...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>12</th>
          <td>25</td>
          <td>Agent_2</td>
          <td>tall</td>
          <td>You are a 25-year-old tall woman who prefers t...</td>
          <td>My favorite t-shirt is a soft, oversized white...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAoccKU47K64FjhSs5iME5LBvG...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>13</th>
          <td>25</td>
          <td>Agent_2</td>
          <td>tall</td>
          <td>You are a 25-year-old tall woman who prefers t...</td>
          <td>My favorite t-shirt is a heather gray, soft co...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmtaNdRgVUx3AgmCPxzTsxQmm1Y...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>14</th>
          <td>25</td>
          <td>Agent_2</td>
          <td>tall</td>
          <td>You are a 25-year-old tall woman who prefers t...</td>
          <td>My favorite hat is a wide-brimmed black fedora...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmB4mHAiCgjF0VUkdLlbB4niWHN...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>15</th>
          <td>25</td>
          <td>Agent_2</td>
          <td>tall</td>
          <td>You are a 25-year-old tall woman who prefers t...</td>
          <td>My favorite hat is a wide-brimmed, floppy sun ...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmuYjcqiJjPc2OnrQb1PHjLFpfK...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>16</th>
          <td>25</td>
          <td>Agent_2</td>
          <td>tall</td>
          <td>You are a 25-year-old tall woman who prefers t...</td>
          <td>My favorite sweater is a cozy oversized knit i...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAiV7LLJy4oAJSwVU2gUcwbkW7...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>17</th>
          <td>25</td>
          <td>Agent_2</td>
          <td>tall</td>
          <td>You are a 25-year-old tall woman who prefers t...</td>
          <td>My favorite sweater is a cozy, oversized turtl...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmudG3DlMX60phP4xBsicVyCLkf...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>18</th>
          <td>45</td>
          <td>Agent_3</td>
          <td>short</td>
          <td>You are a 45-year-old short woman who prefers ...</td>
          <td>My favorite t-shirt is a soft, grey V-neck wit...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAVGeNKF5InLUKrB4RVt9URzqj...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>19</th>
          <td>45</td>
          <td>Agent_3</td>
          <td>short</td>
          <td>You are a 45-year-old short woman who prefers ...</td>
          <td>My favorite t-shirt is a classic, fitted black...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmtONenP8w2It4LUeYhh2oZqxlJ...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>20</th>
          <td>45</td>
          <td>Agent_3</td>
          <td>short</td>
          <td>You are a 45-year-old short woman who prefers ...</td>
          <td>My favorite hat is a cozy knit beanie in a dar...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmA5MmHTeWnkQVI42vT3IAlVpcs...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>21</th>
          <td>45</td>
          <td>Agent_3</td>
          <td>short</td>
          <td>You are a 45-year-old short woman who prefers ...</td>
          <td>My favorite hat is a cozy, knit beanie that I ...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmucl3Xr80F5zV1kts5o14a8OXW...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>22</th>
          <td>45</td>
          <td>Agent_3</td>
          <td>short</td>
          <td>You are a 45-year-old short woman who prefers ...</td>
          <td>My favorite sweater is a cozy, oversized knit ...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAhQovb0WGc3ftUdj5LOh1M3K7...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>23</th>
          <td>45</td>
          <td>Agent_3</td>
          <td>short</td>
          <td>You are a 45-year-old short woman who prefers ...</td>
          <td>My favorite sweater is a cozy, oversized turtl...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmugDO6bl5uXGP7brPPF2MKIuXn...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>24</th>
          <td>45</td>
          <td>Agent_4</td>
          <td>average</td>
          <td>You are a 45-year-old average woman who prefer...</td>
          <td>My favorite t-shirt is a soft, grey V-neck wit...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAaGJoQ6MGbz49FSAgP8JplWvw...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>25</th>
          <td>45</td>
          <td>Agent_4</td>
          <td>average</td>
          <td>You are a 45-year-old average woman who prefer...</td>
          <td>My favorite t-shirt is a soft, heather gray on...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmt05MAS2e7tBBk5I6FqAJF132C...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>26</th>
          <td>45</td>
          <td>Agent_4</td>
          <td>average</td>
          <td>You are a 45-year-old average woman who prefer...</td>
          <td>My favorite hat is a cozy knit beanie with a f...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAEXXlsbjP0b4wozpb5xjVrjF7...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>27</th>
          <td>45</td>
          <td>Agent_4</td>
          <td>average</td>
          <td>You are a 45-year-old average woman who prefer...</td>
          <td>My favorite hat is a cozy, chunky knit beanie ...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmujWuEo2TKV6pxqLV7NQE3jdYC...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>28</th>
          <td>45</td>
          <td>Agent_4</td>
          <td>average</td>
          <td>You are a 45-year-old average woman who prefer...</td>
          <td>My favorite sweater is a cozy, oversized knit ...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmBY6qOiWVMT9ejak6Neceho9ZV...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>29</th>
          <td>45</td>
          <td>Agent_4</td>
          <td>average</td>
          <td>You are a 45-year-old average woman who prefer...</td>
          <td>My favorite sweater is a cozy, oversized cable...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmtNGySJkQepUtOYJyO24Dfct6L...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>30</th>
          <td>45</td>
          <td>Agent_5</td>
          <td>tall</td>
          <td>You are a 45-year-old tall woman who prefers t...</td>
          <td>My favorite t-shirt is a soft, gray V-neck wit...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmApg3WMmsxhHGCQvYoQmbRNnKk...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>31</th>
          <td>45</td>
          <td>Agent_5</td>
          <td>tall</td>
          <td>You are a 45-year-old tall woman who prefers t...</td>
          <td>My favorite t-shirt is a soft, vintage-style c...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmtMaqKc9XqSAUFG2qfUkxhFfk1...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>32</th>
          <td>45</td>
          <td>Agent_5</td>
          <td>tall</td>
          <td>You are a 45-year-old tall woman who prefers t...</td>
          <td>My favorite hat is a wide-brimmed straw hat th...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAuZ0wrUje85kIa5B2K44XP1LZ...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>33</th>
          <td>45</td>
          <td>Agent_5</td>
          <td>tall</td>
          <td>You are a 45-year-old tall woman who prefers t...</td>
          <td>My favorite hat is a sleek, wide-brimmed fedor...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmtq3KX9z5836h0LDpufFqrmjIx...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>34</th>
          <td>45</td>
          <td>Agent_5</td>
          <td>tall</td>
          <td>You are a 45-year-old tall woman who prefers t...</td>
          <td>My favorite sweater is a cozy oversized knit i...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmA7kRJIZF5FchRN8qpWBfpKGRB...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>35</th>
          <td>45</td>
          <td>Agent_5</td>
          <td>tall</td>
          <td>You are a 45-year-old tall woman who prefers t...</td>
          <td>My favorite sweater is a cozy, oversized turtl...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmulpAMtw7dSA4x4NwEqcJq4mIR...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>36</th>
          <td>65</td>
          <td>Agent_6</td>
          <td>short</td>
          <td>You are a 65-year-old short woman who prefers ...</td>
          <td>My favorite t-shirt is a soft, worn-in gray sh...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmA4OEhBOXzsR31tFEZbT4jgwnG...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>37</th>
          <td>65</td>
          <td>Agent_6</td>
          <td>short</td>
          <td>You are a 65-year-old short woman who prefers ...</td>
          <td>My favorite t-shirt is a lovely soft cotton bl...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmtQ7kQGIX0dvGB2PgPABGF2VE3...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>38</th>
          <td>65</td>
          <td>Agent_6</td>
          <td>short</td>
          <td>You are a 65-year-old short woman who prefers ...</td>
          <td>My favorite hat is a cozy knit beanie with a p...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmBQGnyGFk9a23BfXxEEe5lLmdU...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>39</th>
          <td>65</td>
          <td>Agent_6</td>
          <td>short</td>
          <td>You are a 65-year-old short woman who prefers ...</td>
          <td>My favorite hat is a lovely wide-brimmed sun h...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmuzSiApQnWkSgMkUjJP1pytqIg...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>40</th>
          <td>65</td>
          <td>Agent_6</td>
          <td>short</td>
          <td>You are a 65-year-old short woman who prefers ...</td>
          <td>My favorite sweater is a cozy cashmere pullove...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAu0AlDDAurrWPVF0vRsgKnOtL...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>41</th>
          <td>65</td>
          <td>Agent_6</td>
          <td>short</td>
          <td>You are a 65-year-old short woman who prefers ...</td>
          <td>My favorite sweater is a cozy, chunky knit car...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmua52DRGjxXvd9B6htIvdl24Ao...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>42</th>
          <td>65</td>
          <td>Agent_7</td>
          <td>average</td>
          <td>You are a 65-year-old average woman who prefer...</td>
          <td>My favorite t-shirt is a soft, gray V-neck wit...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAT4s8HP5R0gkHcznkCgBOdJbm...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>43</th>
          <td>65</td>
          <td>Agent_7</td>
          <td>average</td>
          <td>You are a 65-year-old average woman who prefer...</td>
          <td>My favorite t-shirt is a soft, cotton blend wi...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmuDomfWWiDCQvO6nDfjdiPnUtV...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>44</th>
          <td>65</td>
          <td>Agent_7</td>
          <td>average</td>
          <td>You are a 65-year-old average woman who prefer...</td>
          <td>My favorite hat is a wide-brimmed straw hat wi...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAfzuUYbXZNy0slRaFEi4xQp5o...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>45</th>
          <td>65</td>
          <td>Agent_7</td>
          <td>average</td>
          <td>You are a 65-year-old average woman who prefer...</td>
          <td>My favorite hat is a cozy, knitted beanie that...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmtZIFugmxx4aC2rl9j8WhIUt1e...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>46</th>
          <td>65</td>
          <td>Agent_7</td>
          <td>average</td>
          <td>You are a 65-year-old average woman who prefer...</td>
          <td>My favorite sweater is a cozy, oversized knit ...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAxZXdQl9KUJrGLmKcBjIH3z0T...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>47</th>
          <td>65</td>
          <td>Agent_7</td>
          <td>average</td>
          <td>You are a 65-year-old average woman who prefer...</td>
          <td>My favorite sweater is a cozy, oversized cable...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmtjDfsCynQDFQodo3jcFDHXgCp...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>48</th>
          <td>65</td>
          <td>Agent_8</td>
          <td>tall</td>
          <td>You are a 65-year-old tall woman who prefers t...</td>
          <td>My favorite t-shirt is a soft, light blue shir...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAC1xvYUF73C3IjNUyBXAtwUuL...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>49</th>
          <td>65</td>
          <td>Agent_8</td>
          <td>tall</td>
          <td>You are a 65-year-old tall woman who prefers t...</td>
          <td>My favorite t-shirt is a classic, comfortable ...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmuBMVGdYxOBROTfdypkHDgoS2N...</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>50</th>
          <td>65</td>
          <td>Agent_8</td>
          <td>tall</td>
          <td>You are a 65-year-old tall woman who prefers t...</td>
          <td>My favorite hat is a wide-brimmed straw hat wi...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAwc7Zej4A8bcHnrsMI5EYMvbv...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>51</th>
          <td>65</td>
          <td>Agent_8</td>
          <td>tall</td>
          <td>You are a 65-year-old tall woman who prefers t...</td>
          <td>My favorite hat is a classic, wide-brimmed sun...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmuU5KKnWvQmseY4HsSQ8i5nH4w...</td>
          <td>hat</td>
        </tr>
        <tr>
          <th>52</th>
          <td>65</td>
          <td>Agent_8</td>
          <td>tall</td>
          <td>You are a 65-year-old tall woman who prefers t...</td>
          <td>My favorite sweater is a cozy, oversized knit ...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-3.5-turbo</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmAVC7xkd5ChqUOIpGHD7uMeSqu...</td>
          <td>sweater</td>
        </tr>
        <tr>
          <th>53</th>
          <td>65</td>
          <td>Agent_8</td>
          <td>tall</td>
          <td>You are a 65-year-old tall woman who prefers t...</td>
          <td>My favorite sweater is a cozy, oversized turtl...</td>
          <td>0</td>
          <td>1000</td>
          <td>gpt-4-1106-preview</td>
          <td>0</td>
          <td>0.5</td>
          <td>1</td>
          <td>1</td>
          <td>{'text': "You are answering questions as if yo...</td>
          <td>{'text': 'You are being asked the following qu...</td>
          <td>{'id': 'chatcmpl-92jmuxHMtxQ8KDTS6gegyQ8F97PzM...</td>
          <td>sweater</td>
        </tr>
      </tbody>
    </table>
    </div>



We can show the schema of the results with the ``show_schema`` method,
which requires a ``shape`` argument (``shape="long"`` or
``shape="wide"``).

Note that using ``shape="wide"`` in the ``sql`` method above displayed
all columns horizontally, whereas ``shape="long"`` displays them
vertically with key-value pairs of column names and values:

.. code:: python

    results.show_schema(shape="long")


.. parsed-literal::

    Type: table, Name: self, SQL: CREATE TABLE self (
                    id INTEGER,
                    data_type TEXT,
                    key TEXT, 
                    value TEXT
                )
    


.. code:: python

    results.sql("select * from self", shape="long")




.. raw:: html

    <div>
    <style scoped>
        .dataframe tbody tr th:only-of-type {
            vertical-align: middle;
        }
    
        .dataframe tbody tr th {
            vertical-align: top;
        }
    
        .dataframe thead th {
            text-align: right;
        }
    </style>
    <table border="1" class="dataframe">
      <thead>
        <tr style="text-align: right;">
          <th></th>
          <th>id</th>
          <th>data_type</th>
          <th>key</th>
          <th>value</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th>0</th>
          <td>0</td>
          <td>agent</td>
          <td>persona</td>
          <td>You are a 25-year-old short woman who prefers ...</td>
        </tr>
        <tr>
          <th>1</th>
          <td>0</td>
          <td>agent</td>
          <td>age</td>
          <td>25</td>
        </tr>
        <tr>
          <th>2</th>
          <td>0</td>
          <td>agent</td>
          <td>height</td>
          <td>short</td>
        </tr>
        <tr>
          <th>3</th>
          <td>0</td>
          <td>agent</td>
          <td>agent_name</td>
          <td>Agent_0</td>
        </tr>
        <tr>
          <th>4</th>
          <td>0</td>
          <td>scenario</td>
          <td>item</td>
          <td>t-shirt</td>
        </tr>
        <tr>
          <th>...</th>
          <td>...</td>
          <td>...</td>
          <td>...</td>
          <td>...</td>
        </tr>
        <tr>
          <th>859</th>
          <td>53</td>
          <td>model</td>
          <td>model</td>
          <td>gpt-4-1106-preview</td>
        </tr>
        <tr>
          <th>860</th>
          <td>53</td>
          <td>answer</td>
          <td>favorite</td>
          <td>My favorite sweater is a cozy, oversized turtl...</td>
        </tr>
        <tr>
          <th>861</th>
          <td>53</td>
          <td>prompt</td>
          <td>favorite_user_prompt</td>
          <td>{'text': 'You are being asked the following qu...</td>
        </tr>
        <tr>
          <th>862</th>
          <td>53</td>
          <td>prompt</td>
          <td>favorite_system_prompt</td>
          <td>{'text': "You are answering questions as if yo...</td>
        </tr>
        <tr>
          <th>863</th>
          <td>53</td>
          <td>raw_model_response</td>
          <td>favorite_raw_model_response</td>
          <td>{'id': 'chatcmpl-92jmuxHMtxQ8KDTS6gegyQ8F97PzM...</td>
        </tr>
      </tbody>
    </table>
    <p>864 rows × 4 columns</p>
    </div>



Visualizations
^^^^^^^^^^^^^^

Built-in visualization methods include: ``.word_cloud_plot()``
``.bar_chart()`` ``.faceted_bar_chart()`` ``.histogram_plot()``

and an interactive html method:
``.select(...).print(html=True, pretty_labels = {...}, interactive = True)``

To visualize a subset of results, we can first apply the ``filter``
method.

.. code:: python

    results.word_cloud_plot("favorite")

.. code:: python

    results_shopping.bar_chart("q_mc", title = q_mc.question_text)

.. code:: python

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
    scenarios = [Scenario({"item": i}) for i in ["books", "electronics", "vacation homes"]]
    results = q_mc.by(scenarios).run()
    
    results.faceted_bar_chart("q_mc", "item", title = "Shopping frequency")

.. code:: python

    q_ls = QuestionLinearScale(
        question_name = "q_ls",
        question_text = "On a scale of 0-10, how much do you typically enjoy shopping for {{ item }}? (0 = Not at all, 10 = Very much)",
        question_options = [0,1,2,3,4,5,6,7,8,9,10]
    )
    scenarios = [Scenario({"item": i}) for i in ["books", "electronics", "vacation homes"]]
    agents = [Agent(traits = {"persona": p}) for p in ["You are a 45-year-old woman who prefers to shop online.", "You are a 25-year-old man who prefers to shop in person."]]
    results = q_ls.by(scenarios).by(agents).run()
    
    results.filter("item == 'books'").histogram_plot("q_ls", title = "Shopping enjoyment")

--------------

.. raw:: html

   <p style="font-size: 14px;">

Copyright © 2024 Expected Parrot, Inc. All rights reserved.
www.expectedparrot.com

.. raw:: html

   </p>

Created in Deepnote
