.. _teaching:

Teaching guide
==============

This page provides a short guide for getting started using EDSL to conduct AI research and collaborate with others.

1. **Create an account**

`Create an account <https://www.expectedparrot.com/login>`_ at Expected Parrot. 
This allows you to access special features for storing, sharing and collaborating on your EDSL projects.
Your account comes with an `API key <https://docs.expectedparrot.com/en/latest/api_keys.html>`_ to access all available language models (see information about `current models <https://www.expectedparrot.com/models>`_) and free `credits <https://docs.expectedparrot.com/en/latest/credits.html>`_ for getting started. 

2. **Install the EDSL package**

Open your terminal or command prompt, navigate to the directory where you want to install the EDSL library, and run the following command:

.. code-block:: bash

    pip install edsl

*Prerequisites:* You must also have Python version 3.9-3.13 and pip installed on your computer.
See the :ref:`installation` section for more details.

3. **Open a Python environment**

After installing EDSL, you can start using it in a Python IDE or text editor of your choice, such as Jupyter Notebook or Visual Studio Code.
Save a new notebook in the directory where you installed EDSL and open it.

You can also start working in EDSL by downloading an example notebook and modifying the code as needed for your research.
See the **How-to Guides** and **Notebooks** for various use cases listed in the sidebar of the `documentation <https://docs.expectedparrot.com/en/latest/index.html>`_ page, and a :ref:`starter_tutorial`.

*Note:* If you are using Google Colab, please see `special instructions <https://docs.expectedparrot.com/en/latest/colab_setup.html>` on storing and accessing your Expected Parrot API key.

4. **Design your research**

EDSL allows you to design AI research projects as surveys of questions administered to language models (optionally) using AI agents to answer the questions.
A typical workflow consists of the following steps:

    - **Create questions**: Construct :ref:`questions` you want to ask a language model. EDSL provides many common question types that you can choose from based on the form of the response that you want to get back from a model (multiple choice, free text, linear scale, etc.). You can also use built-in methods for importing data to use as :ref:`scenarios` of your questions (CSV, PDF, PNG, MP4, DOC, tables, lists, dicts, etc.). This can be efficient for data labeling and other workflows where you want to repeat questions with different data inputs.

    - **Construct a survey**: Combine your questions into :ref:`surveys` to administer them together, and add desired logic, such as skip/stop rules, randomization, piping answers, and more.
    
    - **Design AI agents**: Specify relevant personas and instructions for AI agents to answer the questions (this is optional).
    
    - **Select language models**: Choose the :ref:`language_models` you want to use to generate the answers.
    
    - **Run experiments**: Administer a survey with AI agents and selected language models. This generates a formatted dataset of results. 
    
    - **Analyze results**: Use built-in methods to analyze your :ref:`results`.
    
    - **Validate with humans**: Launch your survey with human respondents to compare the AI-generated responses. Iterate on your survey design and rerun.

5. **Example code**

Below is example code for creating a survey, running it with AI agents and language models, launching it with humans and comparing results.
You can also view the code and output in a downloadable `notebook at Coop <https://www.expectedparrot.com/content/RobinHorton/example-edsl-teaching>`_.

Start by creating a survey:

.. code-block:: python

    from edsl import QuestionMultipleChoice, QuestionNumerical, Survey, Agent, AgentList, Model, ModelList

    # Create questions
    q1 = QuestionMultipleChoice(
        question_name="preferred_source",
        question_text="What is your preferred source of national news?", 
        question_options=["television", "social media", "online news", "newspaper", "radio", "podcast", "other"],
    )
    q2 = QuestionNumerical(
        question_name="hours_per_week",
        question_text="How many hours per week on average do you consume national news via {{ preferred_source.answer }}?" # piping answer from previous question
    )

    # Create a survey
    survey = Survey(questions = [q1, q2])


Run it with AI agents and language models:

.. code-block:: python

    # Create AI agents
    a = AgentList(Agent(traits = {"persona":p}) for p in ["college student", "retired professional"])

    # Select language models
    m = ModelList([
        Model("gpt-4o", service_name = "openai"),
        Model("claude-3-sonnet-20240229", service_name = "anthropic")
    ])

    # Run the survey with the agent and model
    results = survey.by(a).by(m).run()


To see all columns of the results:

.. code-block:: python

    # results.columns 

To inspect components of results:

.. code-block:: python

    results.select("model", "persona", "preferred_source", "hours_per_week")


Example output:

.. list-table::
   :header-rows: 1

   * - model.model
     - agent.persona
     - answer.preferred_source
     - answer.hours_per_week
   * - gpt-4o
     - college student
     - online news
     - 5.0
   * - claude-3-sonnet-20240229
     - college student
     - online news
     - 10.0
   * - gpt-4o
     - retired professional
     - newspaper
     - 2.5
   * - claude-3-sonnet-20240229
     - retired professional
     - online news
     - 10.0


Use built-in methods to analyze results. For example:

.. code-block:: python

    (
        results
            .filter("{{ model.model }} == 'gpt-4o' and {{ agent.persona }} == 'college student'")
            .sort_by("hours_per_week")
            .select("model", "persona", "preferred_source", "hours_per_week", "hours_per_week_comment")
    )

Example output:

.. list-table::
   :header-rows: 1

   * -
     - model.model
     - agent.persona
     - answer.preferred_source
     - answer.hours_per_week
     - comment.hours_per_week_comment
   * - gpt-4o
     - college student
     - online news
     - 5.0
     - I usually check the news online for about 30-45 minutes a day to stay updated, especially with everything going on in the world.
 
 
.. code-block:: python

    results.sql("""
    select 
        model, 
        persona, 
        preferred_source, 
        preferred_source_comment
    from self
    where 1=1 
        and persona == 'retired professional'
        and model == 'claude-3-sonnet-20240229'
    """)


Example output:

.. list-table::
   :header-rows: 1

   * - model
     - persona
     - preferred_source
     - preferred_source_comment
   * - claude-3-sonnet-20240229
     - retired professional
     - online news
     - # As a retired professional, I prefer online news sources as they allow me to easily access a wide variety of reputable national and international news outlets at my convenience. Online news is also frequently updated throughout the day.


To generate a web-based version to share with human respondents:

.. code-block:: python

    web_info = survey.humanize()
    web_info


Example output:

.. code-block:: text 

    {'project_name': 'Project',
    'uuid': 'cd3dff38-9979-4966-b595-ed9fc6e61362',
    'admin_url': 'https://www.expectedparrot.com/home/projects/cd3dff38-9979-4966-b595-ed9fc6e61362',
    'respondent_url': 'https://www.expectedparrot.com/respond/cd3dff38-9979-4966-b595-ed9fc6e61362'}

    
Import the responses:

.. code-block:: python

    from edsl import Coop

    coop = Coop()

    human_results = coop.get_project_human_responses(info["uuid"])


Combine human and AI results:

.. code-block:: python

    combined_results = results + human_results

    combined_results.select("model", "agent_name", "preferred_source", "hours_per_week")


Example output:

.. list-table::
   :header-rows: 1

   * - model.model
     - agent.agent_name
     - answer.preferred_source
     - answer.hours_per_week
   * - gpt-4o
     - Agent_0
     - online news
     - 5.000000
   * - claude-3-sonnet-20240229
     - Agent_1
     - online news
     - 10.000000
   * - gpt-4o
     - Agent_2
     - newspaper
     - 2.500000
   * - claude-3-sonnet-20240229
     - Agent_3
     - online news
     - 10.000000
   * - test
     - 50c21352-0c94-4370-b50f-32b7847895e3
     - newspaper
     - 7.000000
   * - test
     - a2765047-02c3-4040-ab90-549d12778d96
     - social media
     - 5.000000


6. **Share and collaborate**
Results are automatically stored at your account.
You can also post any other EDSL objects to your account from your workspace.
For example, to share a notebook of your code:

.. code-block:: python

    from edsl import Notebook

    nb = Notebook("my_notebook.ipynb")

    nb.push(
        description="My EDSL notebook for AI research",
        alias = "my-notebook",
        visibility = "public"  # or "private" or "unlisted" by defauilt
    )