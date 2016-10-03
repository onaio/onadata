Form Submissions
****************

Implements OpenRosa Api |FormSubmissionAPI|

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
