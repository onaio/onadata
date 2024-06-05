Merged Datasets
***************

.. warning:: **Disclaimer: Experimental Feature**

    This feature is experimental. As a result, users may encounter bugs, glitches, or unexpected behavior. While we have taken steps to ensure a stable experience, some functionality may not work as intended. 
    
    Your feedback is invaluable in helping us improve this feature. Please report any issues or provide suggestions to help us enhance the final version. 
    
    Use this feature at your own discretion and be prepared for potential interruptions or performance inconsistencies.


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
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Returns the data from all linked forms. 

.. raw:: html

	<pre class="prettyprint"><b>GET</b> /api/v1/merged-datasets/{pk}/data</pre>


Example
-------

::

        curl -X GET "https://api.ona.io/api/v1/merged-datasets/1/data"

Response
--------

::

        [
                {"date": "2015-05-19", "gender": "male", "age": 32, "name": "Kendy", "_xform_id_string": "form_a"},
                {"date": "2015-05-19", "gender": "female", "age": 41, "name": "Maasai", "_xform_id_string": "form_b"},
                {"date": "2015-05-19", "gender": "male", "age": 21, "name": "Tom", "_xform_id_string": "form_c"}
        ]


For data pagination and advanced filtering options, use endpoint `/api/v1/data/{pk} <https://github.com/onaio/onadata/blob/cc188e5c83caea78421a5a68093789b64265017b/docs/data.rst#get-json-list-of-data-end-points>`_

How data in parent forms differs from and affects the merged xform
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A merged dataset combines data from multiple forms into one form. It creates a new form structure from the intersection of the fields in the forms being merged.

A merged dataset:
 - Does not allow submissions or data edits, this can only be done on the individual forms.
 - Data deleted from the individual forms will also not be present in the merged dataset.
 - Form replacement is not supported.
 - It has it's own form structure, which is not replaceable the same way you could replace an individual form when changing certain aspects of a form.
