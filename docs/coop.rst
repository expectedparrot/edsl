.. _coop:

Coop
====

`Coop <https://www.expectedparrot.com/content/explore>`_ is a free platform for creating, storing and sharing AI-based research. 
It is fully integrated with EDSL, allowing you to post, store and retrieve any objects that you've created with EDSL, together with data, notebooks and other project content. 
You can also explore public content and collaborate on projects privately with other users:

.. image:: static/coop-my-content.png
  :alt: View your content at the Coop
  :align: center
  :width: 100%


.. raw:: html

  <br><br>


Your Coop account also provides access to features for running EDSL surveys and storing results remotely at the Expected Parrot server.
Learn more about these features in the :ref:`remote_inference` and :ref:`remote_caching` sections of the documentation.
  

Getting started
---------------

1. Create an account
^^^^^^^^^^^^^^^^^^^^

`Sign up <a href="https://www.expectedparrot.com/login>`_ with an email address. 

Your account comes with an **Expected Parrot API key** that allows you to:

* Post and share content at Coop
* Run surveys at the Expected Parrot server 
* Use any available models with your surveys 
* Use remote caching for your responses

You can inspect your key and reset it at any time at your `Settings <https://www.expectedparrot.com/home/settings>`_ page:

.. image:: static/home-settings.png
  :alt: Remote inference settings and Expected Parrot API key
  :align: center
  :width: 100%


.. raw:: html
  
  <br><br>


2. Store your Expected Parrot API key
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When remote inference is activated, your survey jobs and results are automatically stored at the Expected Parrot server and accessible at the `Remote inference <https://www.expectedparrot.com/home/remote-inference>`_ page of your account.

You can also post objects to Coop from your workspace, such as `Surveys`, `Agents` and `Notebooks`. To do this, you first need to create a file named `.env` in your EDSL working directory and store your key in it using the following format:

.. code-block:: python

  EXPECTED_PARROT_API_KEY = 'your_key_here'


3. Post objects to Coop
^^^^^^^^^^^^^^^^^^^^^^^

Post objects to the Coop using the `edsl.coop` module and methods. You can set the visibility status of an object when you post it to the Coop or update it later. There are 3 status options:

* `public`: Visible to everyone 
* `private`: Visible to logged in users that you have granted access
* `unlisted`: Visible to anyone with the link but not listed in search results (default)

See below for details on setting and changing the visibility of an object, and examples of methods for uploading, downloading, updating and deleting content at Coop.


4. Explore content
^^^^^^^^^^^^^^^^^^

Navigate to your `Content <https://www.expectedparrot.com/content>`_ page to see content that you have uploaded:

.. image:: static/coop-my-content.png
  :alt: View your content at the Coop
  :align: center
  :width: 100%


.. raw:: html

  <br><br>


Search other for other users' public content at the `Explore <https://www.expectedparrot.com/content/explore>`_ tab, and copy code and examples to modify or rerun at your workspace.


Methods 
-------

Uploading
^^^^^^^^^

There are 2 methods for uploading/posting an object to Coop:

1. Calling the `push()` method on the object directly
2. Calling the `create()` method on a `Coop` client object and passing it the object

You can optionally pass a `description` and a `visibility` status at the same time: `public`, `private` or `unlisted` (default). 
These can be changed at any time.

**Direct method**

Here we post a question object by calling the `push()` method on it:

.. code-block:: python

  from edsl import QuestionFreeText

  q = QuestionFreeText(
    question_name = "example",
    question_text = "How are you today?"
  )

  q.push() 


This will return information about the object that has been posted, including the URL for viewing it at the Coop web app and the `uuid` for the object which you can use to access it later.
We can see that the object is `unlisted` by default:

.. code-block:: text

  {'description': None,
  'object_type': 'question',
  'url': 'https://www.expectedparrot.com/content/6fb9360c-777d-47cf-bff2-ca80d5787b28',
  'uuid': '6fb9360c-777d-47cf-bff2-ca80d5787b28',
  'version': '0.1.43.dev1',
  'visibility': 'unlisted'}


Here we post the same object with a `description`, a convenient `alias` for the Coop URL and a `visibility` setting (*public*, *private* or *unlisted* by default):

.. code-block:: python

  from edsl import QuestionFreeText

  q = QuestionFreeText(
    question_name = "example",
    question_text = "How are you today?"
  )

  q.push(description="This is an example question", alias = "my-example-question", visibility="public")


We can see the description and visibility status that we specified in the information that is returned:

.. code-block:: text

  {'description': 'This is an example question',
  'object_type': 'question',
  'url': 'https://www.expectedparrot.com/content/65a66d68-6f9e-4b86-8280-b053da53d645',
  'uuid': '65a66d68-6f9e-4b86-8280-b053da53d645',
  'version': '0.1.47.dev1',
  'visibility': 'public'}


**Using a Coop client**

Here we post the same question by passing it to the `create()` method of a `Coop` client object:

.. code-block:: python

  from edsl import Coop, QuestionFreeText

  q = QuestionFreeText(
    question_name = "example",
    question_text = "How are you today?"
  )
  c = Coop()
  c.create(q)


Here we include a description and visibility status:

.. code-block:: python

  from edsl import Coop, QuestionFreeText

  q = QuestionFreeText(
    question_name = "example",
    question_text = "How are you today?"
  )
  c = Coop()
  c.create(object=q, description="This is an example question", alias = "another-example-question", visibility="public")


This will return the same information about the object as the direct method shown above (with a unique `uuid` and URL for viewing the object at the Coop web app).


Updating 
^^^^^^^^

There are 3 methods for updating/editing an object to the Coop:

1. Editing the object at the Coop web app
2. Calling the `patch()` method on the object directly
3. Calling the `patch()` method on a `Coop` client object  

For each `patch()` method, pass the `uuid` of the object and the parameter(s) that you want to update: `description`, `visibility` and/or `value`.

* The `description` parameter is used to update the description of an object, such as a question or survey.
* The `visibility` parameter is used to update the visibility of an object: *public*, *private* or *unlisted*.
* The `value` parameter is used to update the content of an object, such as the text of a question or the code in a notebook.


**At the Coop web app**

You can manually update the `description` or `visibility` of an object at the Coop web app.
Navigate to the `Explore <https://www.expectedparrot.com/content/explore>`_ page and open the page view for an object.
You can select options to change the **visibility** of the object (*public*, *private* or *unlisted*) or to **edit** the description:

.. image:: static/coop-content-object-page.png
  :alt: Page view of an object at Coop
  :align: center
  :width: 100%


.. raw:: html
  
  <br><br>


**Direct method**

Here we update the `description` and `visibility` of the question we created and uploaded in the examples above by calling the `patch()` method on it:

.. code-block:: python

  q.patch(uuid="438e9107-522e-44f2-92e3-925e18da93d1",
          description="This is an updated question", 
          visibility="unlisted")  


This will return a status message:

.. code-block:: text

  {'status': 'success'}


Here we change the question itself by modifying the `value` parameter:

.. code-block:: python

  from edsl import QuestionMultipleChoice
  
  new_q = QuestionMultipleChoice(
    question_name = "example",
    question_text = "How are you today?",
    question_options = ["Good", "Bad", "OK"]
  )
  q.patch(uuid="438e9107-522e-44f2-92e3-925e18da93d1",
          value=new_q)  


**Using a Coop client**

Here we do the same using a `Coop` client object:

.. code-block:: python

  from edsl import Coop

  c = Coop()  
  c.patch(uuid="438e9107-522e-44f2-92e3-925e18da93d1",
          description="This is an updated question",
          visibility="public")  

This will return the same status message as above.


Replicating / Downloading
^^^^^^^^^^^^^^^^^^^^^^^^^

There are a variety of methods for replicating or downloading an object at the Coop:

1. Selecting options to download or copy code at the Coop web app
2. Calling the `pull()` method on the class of the object
3. Calling the `get()` method on a `Coop` client object


**Copy code at the Coop web app**

The Coop web app provides copyable code for downloading or reconstructing an object that has been posted:

* Navigate to the `Explore <https://www.expectedparrot.com/content/explore>`_ page and select an object 
* Go to the object's page 
* Select the option to **Download** the object 

OR

* Select the option to **Pull** the object using its `uuid` or **Raw** to get the code for constructing the object:

.. image:: static/coop-content-object-pull.png
  :alt: Get code for pulling or reconstructing an object on the Coop
  :align: center
  :width: 100%


.. raw:: html
  
  <br><br>


.. image:: static/coop-content-object-raw.png
  :alt: Get code for reconstructing an object on the Coop
  :align: center
  :width: 100%


.. raw:: html
  
  <br><br>


Use this code in your workspace to download the object locally or to reconstruct it.


**Class method**

Here we download the question posted above by calling the `pull()` method on the object class (`Question`) and passing the `uuid` of the object:

.. code-block:: python

  from edsl import Question

  q = Question.pull("438e9107-522e-44f2-92e3-925e18da93d1")
  q


This will return the object (the multiple choice question question that replaced the free text question):

.. list-table::
   :header-rows: 1

   * - key
     - value
   * - question_name
     - example
   * - question_text
     - How are you today?
   * - question_options:0
     - Good
   * - question_options:1
     - Bad
   * - question_options:2
     - OK
   * - question_type
     - multiple_choice


**Using a Coop client**

Here we download the question by calling the `get()` method on a `Coop` client object:

.. code-block:: python

  from edsl import Coop

  c = Coop()
  q = c.get(uuid="438e9107-522e-44f2-92e3-925e18da93d1")
  q


This will return the same object as above.


Deleting
^^^^^^^^

There are 3 methods for deleting an object from the Coop:

1. Selecting options to delete at the Coop web app
2. Calling the `delete()` method on the class of the object
3. Calling the `delete()` method on a `Coop` client object

**At the Coop web app**

You can manually delete objects at the Coop web app:

* Navigate to `Explore <https://www.expectedparrot.com/content/explore>`_ and open an object's page view (see image above for *Uploading* content)
* Select the option to **delete** the object:

.. image:: static/coop-content-object-delete.png
  :alt: Delete an object on the Coop
  :align: center
  :width: 100%


.. raw:: html
  
  <br><br>


**Directly**

Here we delete a question object by calling the `delete()` method on the class of the object (`Question`) and passing the `uuid` of the object:

.. code-block:: python

  from edsl import Question

  Question.delete("1234abcd-abcd-1234-abcd-1234abcd1234")


This will return a status message:

.. code-block:: text

  {'status': 'success'}


**Using a Coop client**

Here we delete a question by calling the `delete()` method on a `Coop` client object, passing the `uuid` of the object:

.. code-block:: python

  from edsl import Coop

  c = Coop()
  c.delete(uuid="1234abcd-abcd-1234-abcd-1234abcd1234")


This will return the same status message as above (so long as the object was not already deleted).



Feature requests
----------------

If you have a feature request for the Coop, please let us know! 
There are several ways to do this:

- Create an issue at `GitHub <https://docs.expectedparrot.com/en/latest/contributing.html#suggesting-enhancements>`_
- Post a message at `Discord <https://discord.com/invite/mxAYkjfy9m>`_
- Send us an email: info@expectedparrot.com



.. automodule:: edsl.coop
  :members:
  :undoc-members:
  :show-inheritance:
  :special-members: __init__
  :exclude-members: 
