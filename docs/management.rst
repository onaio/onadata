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


Restore soft deleted EntityList
-------------------------------

Restores a soft deleted EntityList. The EntityList is identified by its ID or
by the ID of a registration form (XForm) that creates entities in it.

.. code-block:: bash

    python manage.py restore_entity_list entity_list_id

.. code-block:: bash

    python manage.py restore_entity_list --contributor xform_id


Restore submissions to their original version
---------------------------------------------

Restores submissions to the XML they were first submitted with, undoing every edit made since. The submissions are identified by their IDs, or by the ID of their form.

The version being replaced is saved to the submission's history, so it can still be recovered.

Usage
^^^^^

.. code-block:: bash

    python manage.py restore_original_submissions (--instance-ids <id>[,<id>...] | --form-id <form_id>) [--commit-changes]

Options
^^^^^^^

Exactly one of ``--instance-ids`` and ``--form-id`` is required.

- ``--instance-ids``, ``-i``: A submission ID, or several separated by commas with no spaces.
- ``--form-id``, ``-f``: A form ID. Every submission in the form that has been edited is restored.
- ``--commit-changes``, ``-c``: Save the restored XML. If omitted, the command only reports what it would do.

Examples
^^^^^^^^

Report only (no writes):

.. code-block:: bash

    python manage.py restore_original_submissions -i 1,2,3

Restore chosen submissions:

.. code-block:: bash

    python manage.py restore_original_submissions -i 1,2,3 -c

Restore every edited submission in a form:

.. code-block:: bash

    python manage.py restore_original_submissions -f 123 -c

Notes
^^^^^

- One line is printed per submission, stating whether it was restored, skipped or failed.
- A submission is skipped if it is deleted or does not exist, was never edited, or is already at its original version.
- A submission is skipped if its original version is encrypted, or if its earliest history record has no uuid or checksum.
- A failure on one submission is reported and does not stop the rest.
- The restore is recorded as an edit with no user.
- Attachments are not restored. Run ``recover_deleted_attachments --form <form_id>`` afterwards to recover the ones the original XML refers to.
- Webhooks are not triggered.


Soft delete user
----------------

Softs deletes a user. The user is identified by their username and email

.. code-block:: bash

    python manage.py delete_users --user_details username1:email username2:email


Import Entities
---------------

Imports entities from a CSV file into an EntityList.

Usage
^^^^^

.. code-block:: bash

    python manage.py import_entities --entity-list <id> [--created-by <username>] [--dry-run] [--label-column <column_name>] [--uuid-column <column_name>] /path/to/entities.csv

Options
^^^^^^^

- ``--entity-list``: Integer ID of the target EntityList (dataset). Required.
- ``--created-by``: Optional username to attribute creation in Entity history. If omitted, history is attributed to no user.
- ``--dry-run``: Validate and report without creating Entities.
- ``--label-column``: Column name to use as Entity label (default: 'label').
- ``--uuid-column``: Column name to use as Entity UUID (default: 'uuid').

CSV format
^^^^^^^^^^

- A required column for the Entity label. By default, this should be named ``label``, but you can specify a different column name using ``--label-column``.
- An optional column for the Entity UUID. By default, this should be named ``uuid``, but you can specify a different column name using ``--uuid-column``. If provided, it must be unique per Entity within the EntityList. If an Entity with the same uuid already exists, it will be updated instead of creating a new one.
- All other columns are treated as dataset properties and must be defined by forms that create the EntityList (see ``EntityList.properties``). Unknown property columns are silently ignored.
- Empty property values are ignored (not saved).

Example CSV:

.. code-block:: csv

    label,species,circumference_cm,uuid
    300cm purpleheart,purpleheart,300,dbee4c32-a922-451c-9df7-42f40bf78f48
    200cm mora,mora,200,

Examples
^^^^^^^^

Validate only (no writes):

.. code-block:: bash

    python manage.py import_entities --entity-list 123 --dry-run ./trees.csv

Create entities using custom column names:

.. code-block:: bash

    python manage.py import_entities --entity-list 123 --label-column tree_name --uuid-column entity_id ./trees.csv

Notes
^^^^^

- If the specified label column is missing, the command fails with an error.
- Unknown property columns are silently ignored (not saved to entities).
- If an Entity with the same uuid already exists, it will be updated instead of creating a new one.
- Errors are reported with row numbers; when any row fails, the command exits with a non-zero status.
