Starter Tutorial
================

This page provides a guide for getting started running your first
AI-powered research! 

.. raw:: html

    You can also view the contents in an interactive notebook <a href="https://deepnote.com/workspace/expected-parrot-c2fa2435-01e3-451d-ba12-9c36b3b87ad9/project/Expected-Parrot-examples-b457490b-fc5d-45e1-82a5-a66e1738a4b9/notebook/Tutorial%20-%20Starter%20Tutorial-e080f5883d764931960d3920782baf34" target="_blank">here</a>.


Part 1: Using API Keys
----------------------

LLMs are at the heart of AI-powered research. EDSL allows you to easily
conduct research with popular LLMs, including OpenAI's GPTs, Google's
Gemini, Llama 2 and others. In order to do so, you must provide EDSL
with your API keys from LLM providers. EDSL will never store your API
keys.

There are 3 ways that you can provide your API keys to EDSL.

1. Let EDSL ask you for your API keys
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When you first use EDSL in your code, you will be asked to provide API
keys for LLM providers. There are 3 prompts for each of OpenAI, Google
and Deep Infra. Enter the relevant API key when prompted to do so, or
press return to skip entering any key for LLMs that you do not want to
use. Here is an example of how this will look:

.. code:: 

    from edsl.questions import QuestionMultipleChoice

::

   ==================================================
   Please provide your OpenAI API key (https://platform.openai.com/api-keys).
   If you would like to skip this step, press enter.
   If you would like to provide your key, do one of the following:
   1. Set it as a regular environment variable
   2. Create a .env file and add `OPENAI_API_KEY=...` to it
   3. Enter the value below and press enter: 

EDSL will store your API keys in your system’s memory only for the
duration of this session. If you restart your session, you will be asked
for your API keys again.

2. Set your API keys in your Python code
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can also set your API keys in your Python code before you import any
EDSL object as follows:

::

   import os
   os.environ['OPENAI_API_KEY'] = 'your_key_here'
   os.environ['GOOGLE_API_KEY'] = 'your_key_here'
   os.environ['DEEP_INFRA_API_KEY'] = 'your_key_here'

Again, EDSL will store your API keys in your system's memory only for
the duration of this session. If you restart your session, you will be
asked for your API keys again.

Note: You have to provide values for all 3 keys. If you are not planning
to use one of these providers, just input a fake value (such as in the
example above).

3. Use a .env file
~~~~~~~~~~~~~~~~~~

Create a file with the name .env in your working directory and populate
it as follows:

::

   OPENAI_API_KEY=your_key_here
   GOOGLE_API_KEY=your_key_here
   DEEP_INFRA_API_KEY=your_key_here

EDSL will read your API keys from this file. If you restart your
session, you will not be asked for your API keys. This is the
recommended way to provide your API keys, and it will save you a lot of
time in the long run!

Note: You have to provide values for all 3 keys. If you are not planning
to use one of these providers, just input a fake value (such as in the
example above).

Caution
~~~~~~~

You should always treat your API keys like you treat your passwords:
never share them or upload files with your API keys to any public
repository.

Part 2: Conducting AI-powered research
--------------------------------------

With your API keys in place, you're now ready for AI-powered research!
In this part we show how to create and run a simple survey in just a
couple lines of code, and then create a proper survey with only slightly
more work.

Quickstart Example
~~~~~~~~~~~~~~~~~~

Here we create a multiple choice question, prompt an AI agent answer it,
and view the results:

.. code:: 

    # Import the desired question type
    from edsl.questions import QuestionMultipleChoice
    
    # Construct a simple question
    q = QuestionMultipleChoice(
        question_name = "example_question",
        question_text = "How do you feel today?",
        question_options = ["Bad", "OK", "Good"]
    )
    
    # Prompt the default AI agent to answer it (GPT-4)
    results = q.run()
    
    # View the results
    results.select("example_question").print()



.. raw:: html

    <pre style="white-space:pre;overflow-x:auto;line-height:normal;font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace">┏━━━━━━━━━━━━━━━━━━━┓
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> answer            </span>┃
    ┃<span style="color: #800080; text-decoration-color: #800080; font-weight: bold"> .example_question </span>┃
    ┡━━━━━━━━━━━━━━━━━━━┩
    │<span style="color: #7f7f7f; text-decoration-color: #7f7f7f"> Good              </span>│
    └───────────────────┘
    </pre>



A Proper Survey
~~~~~~~~~~~~~~~

Next we'll create a more complex survey, where we ask AI agents how much
they enjoy a certain activity. We can parameterize our survey to ask the
agents' views about various activities. We will also create agents with
different personas, and use different LLMs to create the agents:

.. code:: 

    from edsl.questions import QuestionLinearScale, QuestionFreeText
    from edsl import Scenario, Survey, Agent, Model
    
    # Construct questions - notice the `activity` parameter in the question text
    q1 = QuestionLinearScale(
        question_name = "q1",
        question_text = "On a scale from 0 to 5, how much do you enjoy {{ activity }}?",
        question_options = [0,1,2,3,4,5]
    )
    
    q2 = QuestionFreeText(
        question_name = "q2",
        question_text = "Describe your habits with respect to {{ activity }}."
    )
    
    # Scenarios let us construct multiple variations of the same questions
    activities = ["exercising", "reading", "cooking"]
    scenarios = [Scenario({"activity": a}) for a in activities]
    
    # Combine the questions in a survey
    survey = Survey(questions = [q1, q2])
    
    # Create personas for the agents that will respond to the survey
    personas = ["You are an athlete", "You are a student", "You are a chef"]
    agents = [Agent(traits = {"persona": p}) for p in personas]
    
    # Select LLMs
    models = [Model("gpt-3.5-turbo"), Model("gpt-4-1106-preview")]
    
    # Administer the survey 
    results = survey.by(scenarios).by(agents).by(models).run()
    
    # View the results
    results.select("model.model", "scenario.activity", "agent.persona", "answer.*").print()

.. raw:: html

    View the results in an interactive notebook <a href="https://deepnote.com/workspace/expected-parrot-c2fa2435-01e3-451d-ba12-9c36b3b87ad9/project/Expected-Parrot-examples-b457490b-fc5d-45e1-82a5-a66e1738a4b9/notebook/Tutorial%20-%20Starter%20Tutorial-e080f5883d764931960d3920782baf34" target="_blank">here</a>.


Exploring your results
~~~~~~~~~~~~~~~~~~~~~~

You can use our built-in methods to for analyzing and visualizing your
results. You can also export them as a Pandas dataframe:

.. code:: 

    # Turn the Results object to a pandas dataframe
    results.to_pandas()


.. code:: 

    # The Results object has various attributes you can use
    results.columns


.. parsed-literal::

    ['agent.agent_name',
     'agent.persona',
     'answer.q1',
     'answer.q1_comment',
     'answer.q2',
     'model.frequency_penalty',
     'model.max_tokens',
     'model.model',
     'model.presence_penalty',
     'model.temperature',
     'model.top_p',
     'model.use_cache',
     'prompt.q1_system_prompt',
     'prompt.q1_user_prompt',
     'prompt.q2_system_prompt',
     'prompt.q2_user_prompt',
     'scenario.activity']


.. code:: 

    # The Results object also supports SQL-like queries
    results.sql("select * from self", shape="wide")

.. raw:: html

    View the output and examples of other methods in interactive notebooks <a href="https://deepnote.com/workspace/expected-parrot-c2fa2435-01e3-451d-ba12-9c36b3b87ad9/project/Expected-Parrot-examples-b457490b-fc5d-45e1-82a5-a66e1738a4b9/notebook/Tutorial%20-%20Starter%20Tutorial-e080f5883d764931960d3920782baf34" target="_blank">here</a>.<br><br>
    Learn more about use cases and ways to conduct AI-powered research in the <a href="http://www.expectedparrot.com/getting-started#edsl-showcase" target="_blank">EDSL Showcase</a>.
