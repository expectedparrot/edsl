Building your Research
======================

The EDSL package allows you to conduct AI-powered research by creating
surveys that are answered by large language models.

This notebook introduces you to the core components of EDSL. -
``Question``: a question you would like to ask, that can be created in a
variety of formats - ``Scenario``: optional parameters for your
questions - ``Survey``: a collection of questions - ``Agent``: a persona
for an AI agent that will be prompted to answer your questions -
``Model``: the LLM that you would like to use to power your agents

These components can be combined to create empirical research workflows.
These workflows include but are not limited to survey research: if you
can phrase your task as asking an AI to answer questions, then EDSL will
help you with that.

.. code:: 

    # EDSL should be automatically installed when you run this notebook. If not, run the following command:
    # ! pip install edsl

Questions
---------

Questions are the core building blocks of EDSL workflows. EDSL provides
various question types enable you to get information from LLMs in
specific formats, such as textual responses, lists or numerical answers.

-  Each Question type has a construction method and an answer validation
   method.
-  To use a Question, simply import it and create an instance for
   question you would like to ask.
-  Each Question type has an ``.example()`` method that returns an
   example of a question type:

.. code:: 

    from edsl.questions import QuestionFreeText
    
    # Using the .example() method  
    QuestionFreeText.example()




.. parsed-literal::

    QuestionFreeText(question_text = 'How are you?', question_name = 'how_are_you', allow_nonresponse = True)



.. code:: 

    from edsl.questions import QuestionMultipleChoice
    
    # Creating a question of our own
    q1 = QuestionMultipleChoice(
        question_name = "feel_today",
        question_text = "How do you feel today?",
        question_options = ["good", "bad", "neutral"]
    )
    q1




.. parsed-literal::

    QuestionMultipleChoice(question_text = 'How do you feel today?', question_options = ['good', 'bad', 'neutral'], question_name = 'feel_today', short_names_dict = {})



To learn more about questions, see the Documentation - Questions
notebook.

Surveys
-------

Surveys are collections of questions. Surveys are collections of
questions. By default, each question is asked serially, and respondents
have no memory of previous questions.

.. code:: 

    from edsl import Survey
    
    # the example survey has three questions
    Survey.example()




.. parsed-literal::

    Survey(questions=[QuestionMultipleChoice(question_text = 'Do you like school?', question_options = ['yes', 'no'], question_name = 'q0', short_names_dict = {}), QuestionMultipleChoice(question_text = 'Why not?', question_options = ['killer bees in cafeteria', 'other'], question_name = 'q1', short_names_dict = {}), QuestionMultipleChoice(question_text = 'Why?', question_options = ['**lack*** of killer bees in cafeteria', 'other'], question_name = 'q2', short_names_dict = {})], name=None)



.. code:: 

    # create a survey with two questions
    q2 = QuestionFreeText(
        question_name = "favorite_fruit",
        question_text = "What is your favorite fruit?"
    )
    
    survey = Survey(questions = [q1, q2])
    
    survey




.. parsed-literal::

    Survey(questions=[QuestionMultipleChoice(question_text = 'How do you feel today?', question_options = ['good', 'bad', 'neutral'], question_name = 'feel_today', short_names_dict = {}), QuestionFreeText(question_text = 'What is your favorite fruit?', question_name = 'favorite_fruit', allow_nonresponse = False)], name=None)



To learn more about applying skip logic, see examples in these
notebooks: Skip Logic Constructing Surveys

Agents
------

Agents consist of personas that we prompt LLMs to reference in
responding to questions. An agent is created by passing a persona with
any number of traits. We can optionally give an agent a name, or use the
default name that is created when a survey is administered to the agent.

Here we show the ``.example()`` agent and then construct a set of agents
with different personas:

.. code:: 

    from edsl import Agent 
    
    # the example agent has three traits: "age", "hair", and "height"
    Agent.example()




.. parsed-literal::

    Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5})



.. code:: 

    # constructing three agents with a single "profession" trait
    professions = ["You are an engineer.", "You are a doctor.", "You are a student."]
    
    agents = [Agent(traits = {"profession": p}) for p in professions]
    agents




.. parsed-literal::

    [Agent(traits = {'profession': 'You are an engineer.'}),
     Agent(traits = {'profession': 'You are a doctor.'}),
     Agent(traits = {'profession': 'You are a student.'})]



For more examples of constructing and working with agents, see examples
in this notebook: Designing Agents

Models
------

Models allow you to specify the LLMs that you want to use for your
survey. We can see the available models and select one or more of them
when administering a survey:

.. code:: 

    from edsl import Model
    
    # see the available models
    available_models = Model.available()
    print(f"Available models: {available_models}")
    
    # select one model, and see its parameters
    model = Model('gpt-3.5-turbo')
    model


.. parsed-literal::

    Available models: ['gpt-3.5-turbo', 'gpt-4-1106-preview', 'gemini_pro', 'llama-2-13b-chat-hf', 'llama-2-70b-chat-hf', 'mixtral-8x7B-instruct-v0.1']




.. parsed-literal::

    LanguageModelOpenAIThreeFiveTurbo(model = 'gpt-3.5-turbo', parameters={'temperature': 0.5, 'max_tokens': 1000, 'top_p': 1, 'frequency_penalty': 0, 'presence_penalty': 0, 'use_cache': True})



Scenarios
---------

Scenarios give you an easy way to parameterize your questions.

To use scenarios: - Parameterize your question by using the
``{{ parameter_name }}`` notation in the question text - Create a
scenario by passing a dictionary of parameters to the ``Scenario``
constructor

.. code:: 

    from edsl import Scenario
    
    # Parameterize a question
    q2 = QuestionFreeText(
        question_name = "favorite_thing",
        question_text = "What is your favorite {{ thing }}?"
    )
    
    things = ["color", "fruit", "day of the week"]
    scenarios = [Scenario({"thing": t}) for t in things]

Running Surveys and getting Results
-----------------------------------

To run a survey, you simply need to call its ``.run()`` method. To add
agents, models, and scenarios to your survey, you can use the ``.by()``
method. By default, the survey is administered to Agents without any
traits, and using OpenAI’s GPT-4 model.

Results are the output of administering your survey. The Results object
does not only contain the answers to your questions, but it also comes
with methods that help you to explore and visualize your data.

.. code:: 

    # create a survey with the components we constructed throughout, and run it
    survey = Survey([q1,q2])
    results = survey.by(scenarios).by(agents).by(model).run()
    
    results.select("profession","feel_today", "favorite_thing").print()



.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> agent                </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answer      </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answer                                                                     </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .profession          </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .feel_today </span>┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .favorite_thing                                                            </span>┃
    ┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> You are an engineer. </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> good        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite color is blue.                                                 </span>│
    ├──────────────────────┼─────────────┼────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> You are an engineer. </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> good        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite fruit is definitely mango. I love its sweet and juicy flavor.  </span>│
    ├──────────────────────┼─────────────┼────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> You are an engineer. </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> good        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite day of the week is Saturday because I get to relax and spend   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> time with my family and friends.                                           </span>│
    ├──────────────────────┼─────────────┼────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> You are a doctor.    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> good        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite color is blue.                                                 </span>│
    ├──────────────────────┼─────────────┼────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> You are a doctor.    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> good        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite fruit is definitely mango. It's sweet, juicy, and full of      </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> flavor.                                                                    </span>│
    ├──────────────────────┼─────────────┼────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> You are a doctor.    </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> good        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite day of the week is Saturday because I get to relax and spend   </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> time with my family.                                                       </span>│
    ├──────────────────────┼─────────────┼────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> You are a student.   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> good        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite color is blue.                                                 </span>│
    ├──────────────────────┼─────────────┼────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> You are a student.   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> good        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite fruit is pineapple.                                            </span>│
    ├──────────────────────┼─────────────┼────────────────────────────────────────────────────────────────────────────┤
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> You are a student.   </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> good        </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> My favorite day of the week is Friday because it's the start of the        </span>│
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">                      </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">             </span>│<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> weekend and I can relax after a busy week of studying.                     </span>│
    └──────────────────────┴─────────────┴────────────────────────────────────────────────────────────────────────────┘
    </pre>



To explore built-in methods for analyzing and visualizing results, see
this notebook: Analyzing & Visualizing Results

--------------

.. raw:: html

   <p style="font-size: 14px;">

Copyright © 2024 Expected Parrot, Inc. All rights reserved.
www.expectedparrot.com

.. raw:: html

   </p>

Created in Deepnote
