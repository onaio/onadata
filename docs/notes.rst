Notes
*********

View notes for specific fields in a form.

List all notes to submissions
-----------------------------
.. raw:: html

    <pre class="prettyprint">
    <b>GET</b> /api/v1/notes</pre>

Example
^^^^^^^^
::

       curl -X GET https://api.ona.io/api/v1/notes

Response
^^^^^^^^^
::

        [{
            "id": 4240,
            "id_string": "dhis2form",
            "form": "https://api.ona.io/api/v1/form/1",
        }
        ...

Add a note to a submission
--------------------------
To add notes to a submission you need the following parameters:

- ``note``: the text content of the note
- ``instance``: the submission instance ID you are adding notes on
- ``instance_field``: (optional) The specific question to associate the comment to on the submission instance specified.

.. raw:: html

    <pre class="prettyprint">
    <b>POST</b> /api/v1/notes</pre>

Example
^^^^^^^^
::

       curl -X POST https://api.ona.io/api/v1/notes -d "note=this is a test note" -d "instance=1234"

Response
^^^^^^^^^
::

        [
            {
                "id":1238,
                "note":"This is a test note",
                "date_created":"2016-02-10T13:27:10.299003Z",
                "date_modified":"2016-02-10T13:27:10.299039Z",
                "instance":1234,
                "created_by":1
            }
        ]

Delete a Note
-----------------------------

Where:
 ``pk`` - is the note unique identifier

.. raw:: html

    <pre class="prettyprint">
    <b>DELETE</b> /api/v1/notes/<code>{pk}</code></pre>

Example
^^^^^^^
::

       curl -X DELETE https://api.ona.io/api/v1/notes/1234

Response
^^^^^^^^
::

       HTTP 204 NO CONTENT
