Check active imports
--------------------

.. raw:: html

    <pre class="prettyprint"><b>GET</b> /api/v2/imports/{form_id}</pre>

Example
^^^^^^^
::

       curl -X GET https://api.ona.io/api/v2/imports/{form_id}

Response
^^^^^^^^

::

      [
        {
            "job_uuid": "256dcef5-1baa-48ee-83a3-f7100123f5d2",
            "time_start": "2022-09-29T09:08:59"
        }
    ]


Stops a queued/on-going import task
-----------------------------------

.. raw:: html

    <pre class="prettyprint"><b>DELTE</b> /api/v2/imports/{form_id}?task_uuid={task_uuid}</pre>

Example
^^^^^^^
::

       curl -X DELETE https://api.ona.io/api/v2/imports/{form_id}?task_uuid={task_uuid}

Response
^^^^^^^^

::
    HTTP 204 NO CONTENT


Starts a new Import task for a given form
-----------------------------------

.. raw:: html

    <pre class="prettyprint"><b>POST</b> /api/v2/imports/{form_id}</pre>

Example
^^^^^^^
::

       cur-X POST  -F 'csv_file=@<path to csv file>'  https://api.ona.io/api/v2/imports/{form_id}

Response
^^^^^^^^

::
    {"task_id":"0819b3b0-f0e5-4a6b-83aa-addab20fe208"}
