.. _prolific:

Prolific studies
================

Your Coop account provides an interface to launch your EDSL surveys as studies on Prolific, a platform for recruiting human participants for research studies.
This allows you to gather human responses to your surveys, which can be combined with AI-generated responses for analysis.
You can create a Prolific study from your Coop account, specifying the number of participants, payment amount, and other study details.

A quick demo of the steps below is viewable here.

If you are looking for information about the EDSL method `humanize`, which generates a shareable web-based version of your survey for human respondents, see the :ref:`humanize` page.
This method allows you to collect responses from your own respondents.
The responses can then be combined with AI-generated responses (and Prolific responses) for analysis.

*Please reach out to us if you have any questions or feature requests, or are interested in testing new features for validating AI responses with participants!
You can post a message at our Discord channel or send us an email at info@expectedparrot.com - thank you!*


How it works
------------

1. **Create a survey**: Use EDSL to create a survey, or use the :ref:`survey_builder` interface to build a survey interactively.
Run the survey with AI agents and models to generate responses.
See the :ref:`surveys` section for more details on creating surveys and working with :ref:`results`.

2. **Post the survey to Coop:** Use the `push` method to post the survey to Coop (see example below).
(Surveys created using :ref:`survey_builder` are automatically stored at Coop.)
The survey will automatically appear at your Coop `Content <https://www.expectedparrot.com/content>`_ page, where you can view and manage it.

*Note:* The `push` method can be called on any EDSL object to post it to Coop, including `Survey`, `Agent`, `Model`, `Notebook`, etc.

3. **Create a new project:** At your Coop account, choose the option to create a new project and select the survey you posted.

4. **Create a Prolific study:** Select the option to create a new study and fill in the study details:

   - **Study name** *(Shown to participants)*
   - **Description** *(Shown to participants)*
   - **Required number os participants:** Specify how many participants you want to recruit.
   - **Estimated completion time:** Provide an estimate of how long it will take participants to complete the survey.
   - **Participant payment amount:** Set the payment amount for participants.
   - **Participant allowlist:** Optionally, you can specify a list of Prolific IDs of participants who are allowed to take part in the study.
   - **Configure filters:** Optionally, you can set filters to target specific demographics or characteristics of participants (e.g., age, gender, ethnicity, languages, location, education, work status, etc.).
    
    *Note:* The **Study URL** will be generated automatically. 
    You can open it to view the web-based version of the survey that will be sent to participants.
    (You can also share this link with any other respondents on your own to gather their responses.)

    Click the **Create study** button to finalize the study creation.

5. **Launch the study:** Find the new study at your project dashboard and select the option to launch it.
Responses will automatically appear at your project dashboard where you can review and approve them.

6. **Access results:** Copy the project UUID from the Coop interface and use it to access the participant responses in your EDSL code (see example below).


Example
-------

The example below demonstrates how to create a survey with different question types, run it with an AI agent, and then gather human responses using Prolific.
To create a survey interactively, you can also use the :ref:`survey_builder` interface at your Coop account.

Here we create an EDSL survey run with an AI agent persona and a specified language model.
See the :ref:`questions`, :ref:`surveys`, :ref:`agents` and :ref:`language_models` sections for more details on each of these components.

.. code-block:: python

    # Import modules from EDSL
    from edsl import (
        QuestionYesNo,
        QuestionNumerical,
        QuestionLinearScale,
        Survey,
        Agent,
        Model,
        Coop
    )

    # Create a survey with different question types
    q1 = QuestionYesNo(
        question_name="drive", 
        question_text="Do you drive?"
    )

    q2 = QuestionNumerical(
        question_name="count",
        question_text="How many vehicles do you currently own or lease?",
    )

    q3 = QuestionLinearScale(
        question_name="enjoy",
        question_text="On a scale from 1 to 10, how much do you enjoy driving?",
        question_options=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        option_labels={1: "Hate it", 10: "Love it"},
    )

     # Create a survey with the questions
    survey = Survey(questions=[q1, q2, q3])

    # Create an AI agent to respond to the survey
    agent = Agent(
        traits={
            "persona": "You are a middle-aged mom working on a software startup.",
            "location": "Massachusetts",
        }
    )

    # Select a language model to generate the responses
    model = Model("gemini-1.5-pro", service_name="google")

    # Run the survey with the AI agent and model
    llm_results = survey.by(agent).by(model).run()

    # Inspect the results
    llm_results.select("persona", "location", "drive", "count", "enjoy")


Post the survey to Coop to make it available for human respondents:

.. code-block:: python

    survey.push(
        description = "Survey on vehicle ownership", # optional, stored at Coop content page
        alias = "vehicle-ownership-survey", # optional, used to create a unique URL in addition to the Coop UUID URL
        visibility = "public", # optional, "public" makes it visible to all Coop users, defaults to "unlisted"
    )


`Log into your Coop account <https://www.expectedparrot.com/login>`_ and create a new project and Prolific study for your survey (see steps 3-5 above):

.. image:: static/coop_create_project.png
   :alt: Researcher and respondent options
   :align: center
   :width: 100%


.. raw:: html

   <br>

Use the `Coop` class to import the Prolific results into your EDSL code:

.. code-block:: python

    # Use the Coop class to access Prolific results
    coop = Coop()

    # Copy the project UUID from the Coop interface
    prolific_results = coop.get_project_human_responses("<your_project_uuid>")

    # Combine AI and human results
    combined_results = prolific_results + llm_results  

    # Print the combined results
    combined_results.select("agent_name", "drive", "count", "enjoy")


Learn more about methods for working with results in the :ref:`results` section.


Costs 
-----

Credits for launching Prolific studies are deducted from your Coop credits balance.
The total cost of a Prolific study is calculated based on the number of participants, the payment amount you set for each participant, and the Prolific platform fee for each response.
These costs are displayed in the Coop interface when you create the study, which include the Prolific platform fee and the payment to participants.

You can view your credits balance at your `Credits <https://www.expectedparrot.com/credits>`_ of your Coop account individual transactions at your `Transactions <https://www.expectedparrot.com/transactions>`_ page.



*Please reach out to us if you have any questions or feature requests!
You can post a message at our Discord channel or send us an email at info@expectedparrot.com*