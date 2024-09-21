.. _coop:

Coop
====

The `Coop <https://www.expectedparrot.com/explore>`_ is a platform for creating, storing and sharing LLM-based research. 
It is integrated with the EDSL library, allowing you to post, download and update objects directly from your workspace and at the web app.


How it works
------------

To use the Coop with EDSL, you need to:

1. `Create an account <https://www.expectedparrot.com/login>`_ at the Coop.
2. Store your Expected Parrot API key in your `.env` file.

*Your API key is used to authenticate your account and allow you to post content to the Coop.*


This will allow you to:

* Post content to the Coop: surveys, agents, results, notebooks, files, etc.
* Choose the visibility of your content: *public*, *private* or *unlisted*.
* Explore, download and contribute to other users' shared content.


Remote features
---------------

The Coop also provides access to features for working with EDSL remotely at the Expected Parrot server:

- :ref:`remote_inference`: Run surveys at the Expected Parrot server to save time and resources, and avoid managing your own API keys for language models.
- :ref:`remote_caching`: Automatically store EDSL survey results at the Expected Parrot server to easily access and share them from anywhere. 


1. Create an account
^^^^^^^^^^^^^^^^^^^^

Navigate to the Coop `login page <https://www.expectedparrot.com/login>`_ and select **Sign up**.

.. image:: static/coop_signup.png
  :alt: Create an account at the Coop
  :align: center
  :width: 300px


.. raw:: html

  <br><br>


Create an account with your email address and a password, or log in with your Google or Microsoft account.
If you create an account with your email address, verify it by clicking the link in the email that you receive.


2. Store your Expected Parrot API key
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Navigate to the `Coop API <https://www.expectedparrot.com/home/api>`_ page of your account and copy your API key.


.. image:: static/coop_api_key.png
  :alt: Copy your Expected Parrot API key
  :align: center
  :width: 500px
  

.. raw:: html

  <br><br>


Then add the following line to your `.env` file in your `edsl` working directory (the same file where you store :ref:`api_keys` for language models that you use locally with EDSL):

.. code-block:: python

  EXPECTED_PARROT_API_KEY='<your_api_key_here>'


This will save your Expected Parrot API key as an environment variable that EDSL can access.
You can regenerate your key (and update your `.env` file) at any time.


3. Complete your profile
^^^^^^^^^^^^^^^^^^^^^^^^

Navigate to your `profile page <https://www.expectedparrot.com/home/profile>`_ and choose a username:

.. image:: static/coop_profile_username.png
  :alt: Create a username at your profile
  :align: center
  :width: 500px


.. raw:: html

  <br><br>


Your username will be associated with content that you post on the Coop.
You can change this at any time, and also post content anonymously.


4. Post content to the Coop
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Post objects to the Coop using the `edsl.coop` module and object methods.
You can post files, notebooks and any EDSL objects - `Agent`, `Question`, `Survey`, `Job`, `Results`, `Cache`, etc. - directly from your workspace.
You can set the visibility of an object when you post it to the Coop, or update it later from your workspace or the web app.

For example:

.. code-block:: python 

  from edsl import QuestionMultipleChoice

  q = QuestionMultipleChoice.example()

  q.push(description="This is an example question", visibility="public")


There are 3 visibility options:

* `public`: Visible to everyone 
* `private`: Visible to logged in users that you have granted access
* `unlisted`: Visible to anyone with the link but not listed in search results

By default, objects are posted as *unlisted*.

See below for details and more examples of methods for uploading, downloading, updating and deleting content on the Coop.


5. Explore content
^^^^^^^^^^^^^^^^^^

Search other users' public or privately shared content by object type, keyword, author, topic, etc.
Copy code and examples to modify or rerun them.

*Note:* To access an unlisted object you must have the object `uuid` or URL.



Methods 
-------

Uploading
^^^^^^^^^

There are 2 methods for uploading/posting an object to the Coop:

1. Calling the `push()` method on the object directly
2. Calling the `create()` method on a `Coop` client object and passing it the object

You can optionally pass a `description` and/or `visibility` parameter at the same time: `public`, `private` or `unlisted` (default). 
These can be changed at any time.

**Direct method**
Here we post a question object by calling the `push()` method on it:

.. code-block:: python

  from edsl import QuestionMultipleChoice

  q = QuestionMultipleChoice.example()
  q.push()  


This will return information about the object that has been posted, including the URL for viewing it at the Coop web app and the `uuid` for the object which you can use to access it later.
We can see that the object is `unlisted` by default:

.. code-block:: python

  {'description': None,
  'object_type': 'question',
  'url': 'https://www.expectedparrot.com/content/1234abcd-abcd-1234-abcd-1234abcd1234',
  'uuid': '1234abcd-abcd-1234-abcd-1234abcd1234',
  'version': '0.1.30',
  'visibility': 'unlisted'}


Here we post the same object with a description and visibility:

.. code-block:: python

  from edsl import QuestionMultipleChoice

  q = QuestionMultipleChoice.example()
  q.push(description="This is an example question", visibility="public")


We can see the description and visibility status that we specified in the information that is returned:

.. code-block:: python

  {'description': 'This is an example question',
  'object_type': 'question',
  'url': 'https://www.expectedparrot.com/content/1234abcd-abcd-1234-abcd-1234abcd1234',
  'uuid': '1234abcd-abcd-1234-abcd-1234abcd1234',
  'version': '0.1.30',
  'visibility': 'public'}


**Using a Coop client**
Here we post the same question by passing it to the `create()` method of a `Coop` client object:

.. code-block:: python

  from edsl import Coop, QuestionMultipleChoice

  q = QuestionMultipleChoice.example()
  c = Coop()
  c.create(q)


Here we include a description and visibility status:

.. code-block:: python

  from edsl import Coop, QuestionMultipleChoice

  q = QuestionMultipleChoice.example()
  c = Coop()
  c.create(object=q, description="This is an example question", visibility="public")


This will return the same information about the object as the direct method shown above (with a unique `uuid` and URL for viewing the object at the Coop web app).


Updating 
^^^^^^^^

There are 3 methods for updating/editing an object to the Coop:

1. Editing the object at the Coop web app
2. Calling the `patch()` method on the object directly
3. Calling the `patch()` method on a `Coop` client object  

For each `patch()` method, pass the `uuid` of the object and the parameter(s) that you want to update: 

* `description` 
* `visibility`
* `value`

The `value` parameter is used to update the content of an object, such as the text of a question or the code in a notebook.


**At the Coop web app**
You can manually update the `description` or `visibility` of an object at the Coop web app:

Navigate to **My Content** and select an object: https://www.expectedparrot.com/content/ 

.. image:: static/coop_content.png
  :alt: Select an object on the Coop
  :align: center
  :width: 500px


.. raw:: html

  <br><br>


Go to the object's page (double-click on the object):

.. image:: static/coop_object_page_view.png
  :alt: Open the object's page
  :align: center
  :width: 500px


.. raw:: html

  <br><br>


Select the option to change the **visibility** of the object (*public*, *private* or *unlisted*) or to **edit** the object:

.. image:: static/coop_object_page_view_visibility.png
  :alt: Change the visibility of an object on the Coop
  :align: center
  :width: 500px


.. raw:: html

  <br><br>


.. image:: static/coop_object_page_view_edit.png
  :alt: Edit an object on the Coop
  :align: center
  :width: 500px


.. raw:: html

  <br><br>


**Direct method**
Here we update the `description` and `visibility` of the question created and uploaded in the examples above by calling the `patch()` method on it:

.. code-block:: python

  q.patch(uuid="1234abcd-abcd-1234-abcd-1234abcd1234",
          description="This is an updated question", 
          visibility="public")  


This will return a status message:

.. code-block:: python

  {'status': 'success'}


Here we change the question itself by modifying the `value` parameter:

.. code-block:: python

  from edsl import QuestionFreeText
  
  new_q = QuestionFreeText.example()
  q.patch(uuid="1234abcd-abcd-1234-abcd-1234abcd1234",
          value=new_q)  


**Using a Coop client**
Here we do the same using a `Coop` client object:

.. code-block:: python

  from edsl import Coop

  c = Coop()  
  c.patch(uuid="1234abcd-abcd-1234-abcd-1234abcd1234",
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

* Navigate to **Explore** (or **My Content**) and select an object: https://www.expectedparrot.com/explore/ (see image above for *Uploading* content)
* Go to the object's page (double-click on the object) (see image above for *Uploading* content)
* Select the option to **Download** the object 
OR
* Select the **Code** view of the object, and then **Pull** (to get the code for pulling the object using its `uuid`) or **Raw** (to get the code for constructing the object):

.. image:: static/coop_object_page_view_code_pull.png
  :alt: Get code for pulling or reconstructing an object on the Coop
  :align: center
  :width: 500px


.. raw:: html

  <br><br>


.. image:: static/coop_object_page_view_code_raw.png
  :alt: Get code for reconstructing an object on the Coop
  :align: center
  :width: 500px


.. raw:: html

  <br><br>


Use this code in your workspace to download the object locally or to reconstruct it.


**Class method**
Here we download the question posted above by calling the `pull()` method on the object class (`Question`) and passing the `uuid` of the object:

.. code-block:: python

  from edsl import Question

  q = Question.pull("1234abcd-abcd-1234-abcd-1234abcd1234")
  q


This will return the object (the example free text question that replaced the example multiple choice question):

.. code-block:: python

  {
    "question_name": "how_are_you",
    "question_text": "How are you?",
    "question_type": "free_text"
  }


**Using a Coop client**
Here we download the question by calling the `get()` method on a `Coop` client object:

.. code-block:: python

  from edsl import Coop

  c = Coop()
  q = c.get(uuid="1234abcd-abcd-1234-abcd-1234abcd1234")
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

* Navigate to **My Content** and select an object: https://www.expectedparrot.com/content/ (see image above for *Uploading* content)
* Go to the object's page (double-click on the object) (see image above for *Uploading* content)
* Select the option to **delete** the object:

.. image:: static/coop_object_page_view_delete.png
  :alt: Delete an object on the Coop
  :align: center
  :width: 500px


.. raw:: html

  <br><br>


**Directly**
Here we delete the question object that we posted above by calling the `delete()` method on the class of the object (`Question`) and passing the `uuid` of the object:

.. code-block:: python

  from edsl import Question

  Question.delete("1234abcd-abcd-1234-abcd-1234abcd1234")


This will return a status message:

.. code-block:: python

  {'status': 'success'}


**Using a Coop client**
Here we delete the question by calling the `delete()` method on a `Coop` client object, passing the `uuid` of the object:

.. code-block:: python

  from edsl import Coop

  c = Coop()
  c.delete(uuid="1234abcd-abcd-1234-abcd-1234abcd1234")


This will return the same status message as above (so long as the object was not already deleted).



Feature requests
----------------

If you have a feature request for the Coop, please let us know! 
There are several ways to do this:

- Create an issue on GitHub: https://docs.expectedparrot.com/en/latest/contributing.html#suggesting-enhancements
- Post a message at our Discord server: https://discord.com/invite/mxAYkjfy9m
- Send us an email: info@expectedparrot.com



.. automodule:: edsl.coop
  :members:
  :undoc-members:
  :show-inheritance:
  :special-members: __init__
  :exclude-members: 
