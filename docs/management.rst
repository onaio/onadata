Management Commands
===================

The following custom Django management commands are available:

Regenerate submission JSON
--------------------------

Regenerates the JSON for all submissions of a form.

This is useful in the case where the JSON was saved incorrectly due to some bug when parsing the XML or when saving metadata.

The form is identified by its ID.

.. code-block:: bash

    python manage.py regenerate_submission_json form_id1 form_id2


Restore soft deleted form
-------------------------

Restores a soft deleted form. The form is identified by its ID.

.. code-block:: bash

    python manage.py restore_form form_id

You can also restore a form in Django admin interface:

1. **Navigate to XForms**: Go to the XForm section in the Django admin interface.

2. **Select Forms**: Select the soft-deleted forms you want to restore.

3. **Run Action**: Choose the "Restore selected soft-deleted forms" action from the dropdown menu and click "Go".


Soft delete user
----------------

Softs deletes a user. The user is identified by their username and email

.. code-block:: bash

    python manage.py delete_users --user_details username1:email username2:email
