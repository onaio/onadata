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


Import Entities
---------------

Imports entities from a CSV file into an EntityList.

Usage
^^^^^

.. code-block:: bash

    python manage.py import_entities --entity-list <id> [--created-by <username>] [--dry-run] [--label-column <column_name>] /path/to/entities.csv

Options
^^^^^^^

- ``--entity-list``: Integer ID of the target EntityList (dataset). Required.
- ``--created-by``: Optional username to attribute creation in Entity history. If omitted, history is attributed to no user.
- ``--dry-run``: Validate and report without creating Entities.
- ``--label-column``: Column name to use as Entity label (default: 'label').

CSV format
^^^^^^^^^^

- A required column for the Entity label. By default, this should be named ``label``, but you can specify a different column name using ``--label-column``.
- An optional column named ``uuid``. If provided, it must be unique per Entity within the EntityList. If an Entity with the same uuid already exists, it will be updated instead of creating a new one.
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

Create entities using a custom label column:

.. code-block:: bash

    python manage.py import_entities --entity-list 123 --label-column tree_name ./trees.csv

Notes
^^^^^

- If the specified label column is missing, the command fails with an error.
- Unknown property columns are silently ignored (not saved to entities).
- If an Entity with the same uuid already exists, it will be updated instead of creating a new one.
- Errors are reported with row numbers; when any row fails, the command exits with a non-zero status.
