Coop 
====
Coop is a web application for storing and sharing content created with EDSL and accessing your Expected Parrot API keys.
The `Coop` class provides tools for managing and accessing content in the Coop web application.


Setup
-----
Create an account and log into the Coop:

.. raw:: html

    <a href="https://www.expectedparrot.com/getting-started#coop-create-account">Create an account</a>

Navigate to `Account > API` and get your Coop API key.
Add it to your private `.env` file:

.. code-block:: python 

   EXPECTED_PARROT_API_KEY = "<your_key_here>"


Posting content
---------------
Create a Coop client in your session:

.. code-block:: python 

   from edsl.coop import Coop

   coop = Coop()

Call the `create` method and pass it an EDSL object -- a question, survey, agent or agent list, or results:
By default, all content is publicly viewable by other users.
If you want your content to be private, also pass a parameter `public=False`.
Example:

.. code-block:: python

   from edsl import QuestionMultipleChoice
   q = QuestionMultipleChoice.example()

   coop.create(q, public=False)


Visibility settings 
-------------------
Change the visibility of an object in the Coop by logging in and clicking the button below the object to change it from "Private" to "Public".


Searching for content
---------------------
You can search for content on Coop by using the search bar at the top of the page. 
You can search for content by title, description, tags and author.


Exporting content 
-----------------

1. Exporting content to a file:

2. Exporting content to another platform:

3. Copy code:



Coop class
----------

.. automodule:: edsl.coop.coop
   :members:
   :undoc-members:
   :show-inheritance: