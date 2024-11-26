Management Commands
===================

The following custom Django management commands are available:

Soft delete user
----------------

Softs deletes a user. The user is identified by their username and email

.. code-block:: bash

    python manage.py delete_users --user_details username1:email username2:email


Regenerate submission JSON
--------------------------

Regenerates the JSON for all submissions of a form.

This is useful in the case where the JSON was saved incorrectly due to some bug when parsing the XML.

The form is identified by its ID.

.. code-block:: bash

    python manage.py regenerate_submission_json <form_id1> <form_id2>


Restore soft deleted form
-------------------------

Restores a soft deleted form. The form is identified by its ID.

.. code-block:: bash

    python manage.py restore_form <form_id>
