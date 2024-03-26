Overview
========

What is EDSL? 
-------------

EDSL is an open source python package for creating and running AI-powered research. 
It is designed to make it easy to create and run surveys, data labeling tasks and other research with a large number of AI agents and language models. 

Why EDSL?
---------

Many new LLM packages are focused on providing tools for building agents and real-time systems (e.g., "build a chatbot"). 
Less attention is being paid to the idea of using large numbers of constructed agents to perform large numbers of "tasks", such as answering surveys or labeling data.
With these kinds of tasks, we specifically want to vary the agents and model parameters in order to collect or generate data. 
We also want to perform the tasks as effciently as possible, but they often involve complex interdependencies such as agent memory or skip-logic that make job running non-trivial.
What's needed are tools for creating and running these complex tasks competently, and managing the data that results.

We began building the EDSL package for conducting our own research, but quickly realized there were many common tasks in this "domain" of using LLMs for social science research. 
Rather than working procedurally (*"for agent in agent, for question in survey, for model in model list…"*), we realized a better approach would be a declarative domain-specific language, to provide expressiveness (i.e., make it easy to do a lot with very little code). 

Key components
--------------

EDSL is built around the concept of a "question" that is delivered to an AI "agent" and answered by a large language "model", generating a "result" that can be analyzed, visualized and shared.
Questions of various types (free text, multiple choice, etc.) can be combined into "surveys" and run in parallel or according to specified rules or skip logic (*if q1 result is x then skip to q3*).
Surveys can be run with different agents and models to provide different kinds of responses, and with different "scenarios" that provide context and data to the questions.

The key classes of the package are:

* :ref:`questions`: Building blocks for designing a research project in EDSL. Select among various types of questions based on the desired form of results (free text, multiple choice, etc.). 
* :ref:`surveys`: Collections of questions that can be run in parallel or according to specified rules. Surveys can be run with different agents and models to provide different kinds of responses, and with different "scenarios" that provide context and data to the questions.
* :ref:`agents`: AI agents that "answer" the questions. Agents can have different traits that affect their behavior, such as background or expertise, or "memory" of prior survey responses.
* :ref:`models`: Large language models that generate the responses. EDSL is model agnostic, so questions can be delivered to multiple models for comparison.
* :ref:`scenarios`: Context and data that is passed to questions when they are run. This parameterization of question allows for the same question to be asked in different contexts at scale.
* :ref:`results`: The output of running a question. Results can be analyzed, visualized and shared, and can be used to inform further questions or surveys.

The running of a job--administering a question or survey to an agent and model--is the central operation in EDSL. It is initiated by calling the `run()` method on a question or survey object after it has been optionally configured with agents, models and scenarios using the `by()` method:

.. code-block:: python

    results = survey.by(scenarios).by(agents).by(models).run()

The interplay of these components can be visualized in the following diagram:

< image >

See details about each class and its available methods in the sections below.

Key features 
------------

EDSL is designed to be used in a notebook context, where you can easily run and analyze the results of your research.
It has built-in methods for analysis and visualization of results, and can be readily extended with custom methods.

Coop
^^^^

EDSL is also designed to facilitate sharing of research, code and results. 
The `Coop`_ is a platform for sharing and collaborating on research projects, and is built around the EDSL package.
The Coop provides automatic caching, versioning and sharing of code, data and results, and it designed to work with EDSL the way that GitHub works with git.

EDSL is python-based and plays nicely with existing python tooling.
It is model agnostic, so you can easily present the same questions to different models and agents in parallel to compare results.
It is open source with a permissive license, so you can use it for your own research or build on it for your own projects.

Use cases
---------

EDSL is designed for a wide range of research tasks that involve--or *could* benefit from or be extended by the use of--AI agents and language models, including:

* Simulating surveys and experiments
* Data labeling and classification
* Data augmentation

A quick example of data labeling task in EDSL:

1. Create a question that prompts an agent to classify a text as "positive" or "negative":

.. code-block:: python

    from edsl.questions import QuestionMultipleChoice
    q = QuestionMultipleChoice(
        question_name = "sentiment",
        question_text = "Is this text positive or negative? {{ text }}"
        question_options = ["positive", "negative"]
        )

2. Create a persona for the agent "answering" the question:

.. code-block:: python

    from edsl.agents import Agent
    a = Agent(traits={"persona":"...some description..."})

3. Administer the question to a model and inspect the result:

.. code-block:: python

    from edsl.scenarios import Scenario
    s = Scenario({"text":"...some text..."})

    result = q.by(s).run()
    result.print()

With minimal effort, this code can be extended to include other types of questions (free text, linear scale, etc.), agent traits, models and scenarios, and to run the jobs in parallel or according to specified rules (e.g., *if response is ... then ...*).

Getting help 
------------

EDSL objects have built-in help methods that provide information on their attributes and methods:

.. code-block:: python

    help(object)
    object.example()


PyPI: `https://pypi.org/project/edsl <https://pypi.org/project/edsl/>`_

GitHub: `https://github.com/expectedparrot/edsl <https://github.com/expectedparrot/edsl>`_

Discord: `https://discord.com/invite/mxAYkjfy9m <https://discord.com/invite/mxAYkjfy9m>`_

Email: info@expectedparrot.com