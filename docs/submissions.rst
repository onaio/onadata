===========
Submissions
===========

X Form Submission Api List
==========================

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

    curl -X POST -F xml_submission_file=@/path/to/submission.xml https://ona.io/api/v1/submissions

Submit a JSON XForm submission
--------------------------------

.. raw:: html

	<pre class="prettyprint">
	<b>POST</b> /api/v1/submissions</pre>

Example
^^^^^^^^
::

	       curl -X POST -d '{"id": "[form ID]", "submission": [the JSON]} http://localhost:8000/api/v1/submissions -u user:pass -H "Content-Type: application/json"

Here is some example JSON, it would replace `[the JSON]` above:
::

       {
           "transport": {
               "available_transportation_types_to_referral_facility": \
				["ambulance", "bicycle"],
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
           }
           "meta": {
               "instanceID": "uuid:f3d8dc65-91a6-4d0f-9e97-802128083390"
           }
       }
