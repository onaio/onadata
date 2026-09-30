Management Commands
===================

The following custom Django management commands are available:

Report account usage
--------------------

Export one CSV row per existing personal account or organization, including
inactive accounts, accounts without profiles, and accounts with no submissions.
The configured anonymous system account is excluded.

.. code-block:: bash

    python manage.py report_account_usage --year 2026 --csv account_usage.csv

``--year`` selects the activity calendar year and defaults to ``2026``. Supported
years are 1 through 9998. Omit both output options or use ``--csv -`` to write CSV
to stdout.
Files are written as UTF-8 and cell values use the standard export sanitization
to prevent spreadsheet formulas from being evaluated.

To upload the report to the deployment's configured default storage and print
its download link:

.. code-block:: bash

    python manage.py report_account_usage --year 2026 --storage reports/account_usage_2026.csv

``--storage`` takes a path relative to the default storage root, bucket, or
container. It cannot be combined with ``--csv``. The same command uses Amazon S3
or Azure Blob Storage according to the environment's Django storage settings.
The report is staged in a temporary file, uploaded, and the URL is printed to
stdout. The temporary file is removed automatically.

S3 and Azure use the existing download-link helper, requesting a one-hour URL
with a CSV attachment filename. Access and signing follow the storage backend's
configuration. Other backends use their standard storage URL, which can be a
relative media URL for local filesystem storage. Existing-file overwrite or
rename behavior also follows the backend configuration; the link always uses
the actual saved filename. Use a different path for each report to retain
previous exports.

The columns are:

.. list-table:: Account usage CSV
   :header-rows: 1
   :widths: 30 70

   * - Column
     - Definition
   * - ``account_id``, ``username``
     - The account's user ID and username.
   * - ``account_type``
     - ``personal`` or ``organization``. A user without a profile is personal.
   * - ``total_admin_users``
     - Current organization Owners-team members, excluding the organization
       account itself; one account holder for personal accounts. Includes
       inactive owners, with no join-date or activity filter. An organization
       without an Owners team has zero admins.
   * - ``total_data_collectors``
     - Distinct identified submitting accounts across all retained submissions
       received before report generation.
   * - ``active_data_collectors``
     - Distinct identified submitting accounts during ``activity_year``, up to
       report generation.
   * - ``submissions_last_12_months``
     - Submission records received in the rolling 12 calendar months ending at
       report generation, independent of ``--year``.
   * - ``activity_year``
     - The requested activity year.
   * - ``report_timestamp``
     - Report generation time, captured once and written in ISO 8601 format.
   * - ``rolling_window_start``
     - ISO 8601 timestamp 12 calendar months before ``report_timestamp``.

Calendar boundaries use the deployment's configured ``TIME_ZONE``. Starts are
inclusive and ends exclusive. The activity window ends at the earlier of the
next January 1 and report generation. The rolling window preserves local wall
time; February 29 becomes February 28 in the preceding non-leap year.

Submissions are attributed through their form's project to its current owning
account. Collectors are deduplicated across all of that account's forms and
projects, and an admin who submits data also counts as a collector. Retained
soft-deleted submissions, forms, and projects are included. Receipt time
(``Instance.date_created``) determines activity; edits and submission history
records do not add submissions or change that date.

Anonymous submissions contribute to submission totals but not distinct collector
counts. Counts identify submitting accounts, not individual people using shared
credentials. Transferred projects contribute their retained history to their
current owner. Permanently deleted records and identities cannot be reconstructed;
all-time collector counts cover retained data only.

The command reads accounts in batches and does not create missing profiles or
teams. It does not change database records.

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
