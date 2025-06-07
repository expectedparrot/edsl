.. _humanize:

Humanize
========

EDSL comes with built-in methods for generating web-based versions of your surveys and collecting and analyzing human responses.

*Note:* This page provides information about EDSL code methods for launching surveys, gathering human responses, and analyzing results from your workspace. 
For more information about building surveys interactively, see the :ref:`survey_builder` page.
For more information about launching studies with Prolific participants, see the :ref:`prolific` page.


How it works
------------

1. Create :ref:`surveys` with desired types of :ref:`questions`, and pptionally design AI :ref:`agents` to answer them. Select :ref:`language_models` to generate the responses.

2. Use the `run` method to launch your survey with agents and language models, generating a formatted dataset of :ref:`results`.

3. Use the `humanize` method to generate a web-based version of your survey, with a link for human respondents to access the survey and a link for the admin page at your account where you can access responses interactively.

4. Share the web survey link with human respondents, allowing them to complete the survey. (See the :ref:`prolific` page for information about launching studies with Prolific participants.)

5. Use the `Coop().get_project_human_responses` method to collect the responses in a `Results` object.

6. Analyze the results together with your LLM results, combining insights from both AI and human responses.


Example
-------

Code and results for the example below are also accessible at a downloadable `notebook at Coop <https://www.expectedparrot.com/content/RobinHorton/human-results-example-notebook>`_.

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
    results = survey.by(agent).by(model).run()

    # Generate a web-based version of the survey for human respondents
    web_survey_info = survey.humanize()

    # Create a Coop instance
    coop = Coop()

    # Get human responses from Coop
    human_responses = coop.get_project_human_responses(web_survey_info["uuid"])

    # Combine results (you can add Results objects for the same survey)
    combined_results = results + human_results


*We are continually adding features for launching hybrid LLM and human surveys, so check back for updates!*
*If you are interested in testing new features please reach out at anytime for credits and access.*

