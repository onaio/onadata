Form Submissions
****************

Implements OpenRosa API |FormSubmissionAPI|

.. |FormSubmissionAPI| raw:: html

    <a href="https://bitbucket.org/javarosa/javarosa/wiki/FormSubmissionAPI"
    target="_blank">here</a>


Submit an XML XForm submission
-------------------------------

.. raw:: html

    <pre class="prettyprint">
    <b>POST</b> /api/v1/submissions</pre>

Example
^^^^^^^
::

    curl -X POST -F xml_submission_file=@/path/to/submission.xml https://api.ona.io/api/v1/submissions

.. note:: Authentication may be required depending on your form's permissions. Add ``-u username:password`` to the curl command if needed.

.. important:: If your form is in an organization account and you receive the error ``{"detail":"No XForm matches the given query."}``, use the project-specific submission endpoint instead: ``https://api.ona.io/projects/<project_id>/submission``

Submit a JSON XForm submission
--------------------------------

.. raw:: html

    <pre class="prettyprint">
    <b>POST</b> /api/v1/submissions</pre>

Example
^^^^^^^^
::

    curl -X POST -d '{"id": "[id_string]", "submission": [the JSON]} https://api.ona.io/api/v1/submissions -u user:pass -H "Content-Type: application/json"

.. note:: The ``[id_string]`` here is in the name of your form as exposed in the Ona UI and the ``id_string`` as per the `Forms API <forms.html#get-form-information>`_.

.. important:: If your form is in an organization account and you receive the error ``{"detail":"No XForm matches the given query."}``, use the project-specific submission endpoint instead: ``https://api.ona.io/projects/<project_id>/submission``

Here is some example JSON, it would replace `[the JSON]` above:
::

       {
           "transport": {
               "available_transportation_types_to_referral_facility": ["ambulance", "bicycle"],
               "loop_over_transport_types_frequency": {
                   "ambulance": {
                       "frequency_to_referral_facility": "daily"
                   },
                   "bicycle": {
                       "frequency_to_referral_facility": "weekly"
                   },
                   "boat_canoe": null,
                   "bus": null,
                   "donkey_mule_cart": null,
                   "keke_pepe": null,
                   "lorry": null,
                   "motorbike": null,
                   "taxi": null,
                   "other": null
               }
           },
           "meta": {
               "instanceID": "uuid:f3d8dc65-91a6-4d0f-9e97-802128083390"
           }
       }

Submit a JSON XForm submission using Python
--------------------------------------------

This example demonstrates how to submit JSON data to a form using Python. First, here's an example XLSForm structure:

**Survey worksheet:**

+---------------+--------+----------------------+
| type          | name   | label                |
+===============+========+======================+
| today         | today  |                      |
+---------------+--------+----------------------+
| select_one    | gender | Respondent's gender? |
| gender        |        |                      |
+---------------+--------+----------------------+
| integer       | age    | Respondent's age?    |
+---------------+--------+----------------------+

**Settings worksheet:**

+---------------+---------------+
| form_title    | form_id       |
+===============+===============+
| Sample Survey | sample_survey |
+---------------+---------------+

.. note:: You can download this complete XLSForm example from |SampleXLSForm|.

.. |SampleXLSForm| raw:: html

    <a href="https://docs.google.com/spreadsheets/d/1SNACjATRAAkLvO7WaOrV-JGJhve1hIH4/edit?usp=sharing&ouid=111645668347905426096&rtpof=true&sd=true"
    target="_blank">Google Sheets</a>

**Choices worksheet:**

+-----------+-------------+-------------+
| list_name | name        | label       |
+===========+=============+=============+
| gender    | transgender | Transgender |
+-----------+-------------+-------------+
| gender    | female      | Female      |
+-----------+-------------+-------------+
| gender    | male        | Male        |
+-----------+-------------+-------------+
| gender    | other       | Other       |
+-----------+-------------+-------------+

Python Example
^^^^^^^^^^^^^^

This example uses the ``requests`` library to submit JSON data:

.. important:: If your form is in an organization account and you receive the error ``{"detail":"No XForm matches the given query."}``, use the project-specific submission endpoint instead: ``https://api.ona.io/projects/<project_id>/submission``

::

    import requests
    import uuid
    from datetime import datetime
    from requests.auth import HTTPDigestAuth

    # API endpoint and credentials
    url = "https://api.ona.io/api/v1/submissions"
    username = "your_username"
    password = "your_password"

    # Form ID (id_string) - must match the form_id from the settings worksheet
    form_id = "sample_survey"

    # Prepare the submission data
    submission_data = {
        "id": form_id,
        "submission": {
            "today": datetime.now().strftime("%Y-%m-%d"),
            "gender": "female",
            "age": 28,
            "meta": {
                "instanceID": f"uuid:{uuid.uuid4()}"
            }
        }
    }

    # Make the POST request with digest authentication
    headers = {"Content-Type": "application/json"}
    response = requests.post(
        url,
        json=submission_data,
        auth=HTTPDigestAuth(username, password),
        headers=headers
    )

    # Check the response
    if response.status_code == 201:
        print("Submission successful!")
        print(f"Response: {response.json()}")
    else:
        print(f"Submission failed with status code: {response.status_code}")
        print(f"Error: {response.text}")

.. note:: Make sure to install the requests library first: ``pip install requests``

Submit a FLOIP XForm submission
-------------------------------
To make a FLOIP submission, specify the content type header as ``"Content-Type: application/vnd.org.flowinterop.results+json"`` and the ``[FLOIP data]`` in a list of rows format each row having 6 values.
The FLOIP data format is specified |FLOIPSubmissionAPI|.

.. |FLOIPSubmissionAPI| raw:: html

    <a href="https://github.com/FLOIP/flow-results/blob/master/specification.md#resource-data-found-at-external-path"
    target="_blank">here</a>

The values in each row should be in the following order:
      - ``Timestamp``
      - ``Row ID``
      - ``Contact ID``
      - ``Question ID``
      - ``Response``
      - ``Response metadata``

.. raw:: html

    <pre class="prettyprint">
    <b>POST</b> /<code>{user}</code>/<code>{pk}</code>/submission</pre>

Example
^^^^^^^
::

    curl -X POST https://api.ona.io/[user]/[pk]/submission -H "Content-Type: application/vnd.org.flowinterop.results+json" -d '[FLOIP data]'

Here is an example of what will replace ``[FLOIP data]``:
::

    [
      [ "2017-05-23T13:35:37.356-04:00", 20394823948, 923842093, "ae54d3", "female", {"option_order": ["male","female"]} ],
      [ "2017-05-23T13:35:47.012-04:00", 20394823950, 923842093, "ae54d7", "chocolate", {} ]
    ]

Edit an existing XForm submission
---------------------------------
.. raw:: html

    <pre class="prettyprint">
    <b>POST</b> /api/v1/submissions</pre>

Same request as above for both XML and JSON XForm submission while providing a ``deprecatedID`` and newly generated ``instanceID``.

Example
^^^^^^^^
::

    curl -X POST -d '{"id": "[id_string]", "submission": [the JSON]} https://api.ona.io/api/v1/submissions -u user:pass -H "Content-Type: application/json"

.. important:: When editing an existing submission, ``deprecatedID`` needs to be provided as one of the meta fields. ``deprecatedID`` is the instanceID of the submission which is being updated and ``instanceID`` is the newly generated ``instanceID``. See |OpenRosaMetaDataSchema| for more details.

.. |OpenRosaMetaDataSchema| raw:: html

    <a href="https://bitbucket.org/javarosa/javarosa/wiki/OpenRosaMetaDataSchema"
    target="_blank">OpenRosa MetaData Schema</a>

.. important:: If your form is in an organization account and you receive the error ``{"detail":"No XForm matches the given query."}``, use the project-specific submission endpoint instead: ``https://api.ona.io/projects/<project_id>/submission``

Here is some example JSON provided for updating an existing instance, it would
replace `[the JSON]` above:
::

       {
           "transport": {
               "available_transportation_types_to_referral_facility": ["ambulance", "bicycle"],
               "loop_over_transport_types_frequency": {
                   "ambulance": {
                       "frequency_to_referral_facility": "daily"
                   },
                   "bicycle": {
                       "frequency_to_referral_facility": "weekly"
                   },
                   "boat_canoe": null,
                   "bus": null,
                   "donkey_mule_cart": null,
                   "keke_pepe": null,
                   "lorry": null,
                   "motorbike": null,
                   "taxi": null,
                   "other": null
               }
           },
           "meta": {
               "instanceID": "uuid:f3d8dc65-91a6-4d0f-9e98-802128083390",
               "deprecatedID": "uuid:f3d8dc65-91a6-4d0f-9e97-802128083390"

           }
       }
