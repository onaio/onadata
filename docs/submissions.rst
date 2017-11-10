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

Submit a JSON XForm submission
--------------------------------

.. raw:: html

    <pre class="prettyprint">
    <b>POST</b> /api/v1/submissions</pre>

Example
^^^^^^^^
::

    curl -X POST -d '{"id": "[id_string]", "submission": [the JSON]} http://api.ona.io/api/v1/submissions -u user:pass -H "Content-Type: application/json"

.. note:: The ``[id_string]`` here is in the name of your form as exposed in the Ona UI and the ``id_string`` as per the `Forms API <forms.html#get-form-information>`_.

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

    curl -X POST http://api.ona.io/[user]/[pk]/submission -H "Content-Type: application/vnd.org.flowinterop.results+json" -d '[FLOIP data]'

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

    curl -X POST -d '{"id": "[id_string]", "submission": [the JSON]} http://api.ona.io/api/v1/submissions -u user:pass -H "Content-Type: application/json"

.. important:: When editing an existing submission, ``deprecatedID`` needs to be provided as one of the meta fields. ``deprecatedID`` is the instanceID of the submission which is being updated and ``instanceID`` is the newly generated ``instanceID``. See |OpenRosaMetaDataSchema| for more details.

.. |OpenRosaMetaDataSchema| raw:: html

    <a href="https://bitbucket.org/javarosa/javarosa/wiki/OpenRosaMetaDataSchema"
    target="_blank">OpenRosa MetaData Schema</a>

Here is some example JSON provided for updating an exisiting instance, it would
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
