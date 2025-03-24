.. _checklist:

Survey logic checklist
======================

This page provides a checklist for reviewing the logic and contents of an EDSL survey and ensuring that it will run as you intend it to.


Support 
-------

Please reach out to us with any questions or issues! 
Send an email to **info@expectedparrot.com** or post a message at `Discord <https://discord.com/invite/mxAYkjfy9m>`_.


How EDSL works
^^^^^^^^^^^^^^

At its core, EDSL is built on the concept of :ref:`questions` being answered by AI :ref:`agents`, using :ref:`language_models` to generate responses that are returned as formatted datasets of :ref:`results`.

A typical workflow consists of the following steps:

1. Construct **questions** of different types (multiple choice, free text, etc.) and combine them in a survey. Learn about `question types <https://docs.expectedparrot.com/en/latest/questions.html>`_.
2. *Optional:* Add **data or content** to your questions (from CSVs, PDFs, docs, images, etc.). Learn about `scenarios <https://docs.expectedparrot.com/en/latest/scenarios.html>`_.
3. *Optional:* Add **rules or logic** to specify how questions should be presented (e.g., skip/stop rules, or including context of other questions). Learn about `survey rules <https://docs.expectedparrot.com/en/latest/surveys.html>`_.
4. *Optional:* Design or import **personas** for AI agents to answer the questions. Learn about `agents <https://docs.expectedparrot.com/en/latest/agents.html>`_.
5. Select **language models** to generate responses. EDSL works with hundreds of popular `models <https://docs.expectedparrot.com/en/latest/language_models.html>`_.
6. Run the survey and get a formatted dataset of **results**. Use `built-in methods <https://docs.expectedparrot.com/en/latest/results.html>`_ for analyzing them.
7. *Optional:* Store and share your work at the `Coop <https://www.expectedparrot.com/content/explore>`_: a platform for AI research that is fully integrated with EDSL. `Learn more <https://docs.expectedparrot.com/en/latest/coop.html>`_.


Issues checklist
^^^^^^^^^^^^^^^^

Below are some issues to consider before running a survey, with links to examples of EDSL features for handling them.


Are you using appropriate question types?
-----------------------------------------

Ensure that the question type you are using is appropriate for the question you are presenting.

* Use `QuestionYesNo` when you only want to allow "Yes" or "No" responses.
* Use `QuestionMultipleChoice` when you want to require that only one option be selected.
* Use `QuestionCheckBox` when you want to allow multiple (or no) selections or specify a number of selections.


Are question options correct and complete?
------------------------------------------

Ensure that the question options make sense for the question text.

* Does the question text ask for options not presented, or a different number of options?
* Should the question options include an option for non-responses (e.g., "I do not know.")?
* Are validation constraints appropriate for your use case (e.g., min/max values, required selections)?


Do any questions require context of other questions?
----------------------------------------------------

Survey questions are administered asynchronously by default, meaning that the presentation of one question does not include context of any other questions in the survey unless you specify otherwise. 
This default functionality reduces costs and runtime.
It also allows you to fine-tune and readily compare responses to versions of questions with different contexts. 

If a question depends on or requires information about other questions in a survey, you need to add a rule specifying the logic to be applied.
This can be done in a variety of ways:

* Use `piping <https://docs.expectedparrot.com/en/latest/surveys.html#id2>`_ to add components of a question in another question (e.g., insert the answer to a question in the text of a follow-up question).
* Use question `memory <https://docs.expectedparrot.com/en/latest/surveys.html#question-memory>`_ to include the entire context of a question/answer in the presentation of a different question (*"You were previously asked..."*). There are separate rules for adding the context of a single question, a set of questions, all prior questions, or a lagged number of questions.


Testing a model's ability to answer a question
----------------------------------------------

Running test questions and examining the answers and `"comment" fields <https://docs.expectedparrot.com/en/latest/questions.html#optional-additional-parameters>`_ can help you understand whether a question needs to be improved.
You can also run questions *about* your questions for `cognitive testing <https://docs.expectedparrot.com/en/latest/notebooks/research_methods.html>`_ (e.g., *"How is the following question confusing: {{ question }}"*)


Tools for integrating data
^^^^^^^^^^^^^^^^^^^^^^^^^^

Scenario objects
----------------

EDSL provides many methods for importing and formatting data or content to be used with a survey.
This can be particularly useful for surveys that involve `data labeling <https://docs.expectedparrot.com/en/latest/notebooks/data_labeling_example.html>`_ or `data cleaning <https://docs.expectedparrot.com/en/latest/notebooks/data_cleaning.html>`_ tasks, such as using questions to extract information from unstructured texts or apply labels to images or other content.
This is done by creating `Scenerio` <https://docs.expectedparrot.com/en/latest/scenarios.html>`_ objects representing data or content to be added to survey questions (e.g., *"What is the main topic of this text? {{ text }}?", "What is in this image? {{ image }}"*).
See `examples <https://docs.expectedparrot.com/en/latest/notebooks/question_loop_scenarios.html>`_ for working with `PDFs <https://docs.expectedparrot.com/en/latest/notebooks/scenario_from_pdf.html>`_, CSVs, `images <https://docs.expectedparrot.com/en/latest/notebooks/image_scenario_example.html>`_, docs, `tables <https://docs.expectedparrot.com/en/latest/notebooks/scenario_list_wikipedia.html>`_ and other data types.
You can also use scenarios to store `metadata <https://docs.expectedparrot.com/en/latest/notebooks/adding_metadata.html>`_ for surveys.


Converting questions
--------------------

Many models are highly capable of reformatting non-EDSL surveys based on a prompt that includes basic instructions or examples of EDSL code. 
This can be an efficient way to reconstruct an existing survey in EDSL and then modify as needed with above-mentioned methods.  
See examples: `CES data <https://docs.expectedparrot.com/en/latest/notebooks/ces_data_edsl.html>`_; `GoogleForms <https://docs.expectedparrot.com/en/latest/notebooks/google_form_to_edsl.html>`_.