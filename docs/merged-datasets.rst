Merged Datasets
***************

This endpoint provides access to data from multiple forms. Merged datasets should have the same functionality as the forms endpoint with the difference being:

- They do not accept submissions directly, submissions to individual forms will be reflected in merged datasets..
- No edits are allowed on the merged dataset, edits should be applied on the individual form.

Merged datasets will only display the fields that are common to all the forms that are being merged.

Where:

- ``pk`` - is the merged dataset id

Definition
^^^^^^^^^^
- ``name`` - Name or title of the merged dataset (required)
- ``project`` - Project for the merged dataset (required)
- ``xforms`` - List of forms to merge (required, at least 2 forms should be provided)


Create a new Merged Dataset
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. raw:: html

    <pre class="prettyprint">
    <b>POST</b> /api/v1/merged-datasets</pre>

Example
-------
::

        {
            "name": "My Dataset",
            "xforms": [
                "https://api.ona.io/api/v1/forms/12",
                "https://api.ona.io/api/v1/forms/13"
            ],
            "project":  "https://api.ona.io/api/v1/projects/13"
        }

Response
--------
::

        {
            "title": "My Dataset",
            "url": "https://api.ona.io/api/v1/merged-datasets/14",
            "xforms": [
                "https://api.ona.io/api/v1/forms/12",
                "https://api.ona.io/api/v1/forms/13"
            ],
            "project": "https://api.ona.io/api/v1/projects/13"
        }


Retrieve a Merged Dataset
^^^^^^^^^^^^^^^^^^^^^^^^^

.. raw:: html

    <pre class="prettyprint">
    <b>GET</b> /api/v1/merged-datasets/<code>{pk}</code></pre>

Response
--------

::

        {
            name: "My Dataset",
            url: "https://api.ona.io/api/v1/merged-datasets/1",
            xforms: [
                "https://api.ona.io/api/v1/forms/12",
                "https://api.ona.io/api/v1/forms/13"]
            project: "https://api.ona.io/api/v1/projects/13"
        }

List all Merged Datasets
^^^^^^^^^^^^^^^^^^^^^^^^

.. raw:: html

    <pre class="prettyprint">
    <b>GET</b> /api/v1/merged-datasets</pre>

Response
--------

::


    [
        {
            name: "My Dataset",
            url: "https://api.ona.io/api/v1/merged-datasets/1",
            xforms: [
                "https://api.ona.io/api/v1/forms/12",
                "https://api.ona.io/api/v1/forms/13"]
            project: "https://api.ona.io/api/v1/projects/13"
        }, ...
    ]


Update a Merged Dataset
^^^^^^^^^^^^^^^^^^^^^^^

.. raw:: html

    <pre class="prettyprint">
    <b>PUT</b> /api/v1/merged-datasets/<code>{pk}</code></pre>


Patch a Merged Dataset
^^^^^^^^^^^^^^^^^^^^^^

.. raw:: html

    <pre class="prettyprint">
    <b>PATCH</b> /api/v1/merged-datasets/<code>{pk}</code></pre>


Delete a Merged Dataset
^^^^^^^^^^^^^^^^^^^^^^^

.. raw:: html

    <pre class="prettyprint">
    <b>DELETE</b> /api/v1/merged-datasets/<code>{pk}</code></pre>

Response
--------

::

    HTTP 204 NO CONTENT


Retrieving Data from a Merged Dataset
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Returns the data from both forms. The key `_xform_id_string` can be used to
differentiate data from linked forms.

.. raw:: html

    <pre class="prettyprint">
    <b>GET</b> /api/v1/merged-datasets/<code>{pk}</code>/data
    <b>GET</b> /api/v1/data/<code>{pk}</code>
    </pre>

::

    curl -X GET "https://api.ona.io/api/v1/merged-datasets/1/data"
    curl -X GET "https://api.ona.io/api/v1/data/1"



Example Response
----------------
::


        [
                {"date": "2015-05-19", "gender": "male", "age": 32, "name": "Kendy", "_xform_id_string": "form_a"},
                {"date": "2015-05-19", "gender": "female", "age": 41, "name": "Maasai", "_xform_id_string": "form_b"},
                {"date": "2015-05-19", "gender": "male", "age": 21, "name": "Tom", "_xform_id_string": "form_c"}
        ]

How data in parent forms differs from and affects the merged xform
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A merged dataset combines data from multiple forms into one form. It creates a new form structure from the intersection of the fields in the forms being merged.

A merged dataset:
 - Does not allow submissions or data edits, this can only be done on the individual forms.
 - Data deleted from the individual forms will also not be present in the mereged dataset.
 - Form replacement is not supported.
 - It has it's own form structure, which is not replaceable the same way you could replace an individual form when changing certain aspects of a form.
