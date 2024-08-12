
Entities
========

Entities allow you to share information between forms, enabling the collection of longitudinal data, management of cases over time, and support for other complex workflows.

The following endpoints provides access to Entities related data: Where:

- ``Entity`` - Each item that gets managed by an ODK workflow. Entities are automatically created from submissions receieved from a form that contains entity definitions.
- ``EntityList`` - a dataset that contains Entities of the same type.
- ``entity_list_id`` - An EntityList's unique identifier
- ``entity_id`` - An Entity's unique identifier

Create EntityList
-----------------

.. raw:: html

	   <pre class="prettyprint"><b>POST</b> /api/v2/entity-lists</pre>

This endpoint is used to create a single EntityList dataset within a project. Entities for the dataset can then be created from a form or via the API.

EntityList name must not include ``.`` or start with ``__``

EntityList name is unique per project.

The EntityList by default has no properties.

**Example**

.. code-block:: bash

      curl -X POST "https://api.ona.io/api/v2/entity-lists" \
      -H "Authorization: Token ACCESS_TOKEN" \
      -H "Content-Type: application/json" \
      -d '{
               "name": "trees",
               "project": "2",
         }'

**Response**

Status: ``201 Created``

Body:

.. code-block:: json

      {
         "id":1,
         "name":"trees",
         "project":2,
         "date_created":"2024-06-27T07:35:53.451077Z",
         "date_modified":"2024-06-27T07:35:53.451091Z"
      }

Get a list of EntityLists
-------------------------
.. raw:: html

	   <pre class="prettyprint"><b>GET</b> /api/v2/entity-lists</pre>

This endpoint is used to get all EntityList datasets.

The user must have view permission for each dataset.

The maximum number of items returned is ``1000``. To get more results than this, pagination is required. Refer to getting `paginated results <#paginated-entity-lists>`_ section.


**Example**

.. code-block:: bash

      curl -X GET https://api.ona.io/api/v2/entity-lists

**Response**

Status: ``200 OK``

Body:

.. code-block:: json

      [
         {
            "url":"http://testserver/api/v2/entity-lists/9",
            "id":9,
            "name":"trees",
            "project":"http://testserver/api/v1/projects/9",
            "public":false,
            "datecreated":"2024-04-17T11:26:24.630117Z",
            "datemodified":"2024-04-17T11:26:25.050823Z",
            "numregistrationforms":1,
            "numfollowupforms":1,
            "numentities":1
         }
      ]


Get a list of Entities for a specific project
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. raw:: html

	   <pre class="prettyprint"><b>GET</b> /api/v2/entity-lists?project=&lt;project_id&gt;</pre>

**Example**

.. code-block:: bash

      curl -X GET https://api.ona.io/api/v2/entity-lists?project=9

**Response**

Status: ``200 OK``

Body:

.. code-block:: json

      [
         {
            "url":"http://testserver/api/v2/entity-lists/9",
            "id":9,
            "name":"trees",
            "project":"http://testserver/api/v1/projects/9",
            "public":false,
            "datecreated":"2024-04-17T11:26:24.630117Z",
            "datemodified":"2024-04-17T11:26:25.050823Z",
            "numregistrationforms":1,
            "numfollowupforms":1,
            "numentities":1
         }
      ]


.. _paginated-entity-lists:

Get a paginated list of EntityLists
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. raw:: html

	   <pre class="prettyprint"><b>GET</b> /api/v2/entity-lists?page=&lt;page&gt;&page_size=&lt;page_size&gt;</pre>

Returns a list of projects using page number and the number of items per page. Use the ``page`` parameter to specify page number and ``page_size`` parameter is used to set the custom page size.

- ``page`` - Integer representing the page.
- ``page_size`` - Integer representing the number of records that should be returned in a single page. The maximum number of items that can be requested in a page via the ``page_size`` query param is ``10,000``.

**Example**

.. code-block:: bash

      curl -X GET https://api.ona.io/api/v2/entity-lists?page=1&page_size=100


**Response**

Status: ``200 OK``

Body:

.. code-block:: json

      [
         {
            "url":"http://testserver/api/v2/entity-lists/9",
            "id":9,
            "name":"trees",
            "project":"http://testserver/api/v1/projects/9",
            "public":false,
            "datecreated":"2024-04-17T11:26:24.630117Z",
            "datemodified":"2024-04-17T11:26:25.050823Z",
            "numregistrationforms":1,
            "numfollowupforms":1,
            "numentities":1
         }

      ]


Get EntityList Details
-----------------------

.. raw:: html

	   <pre class="prettyprint"><b>GET</b> /api/v2/entity-lists/&lt;entity_list_id&gt;</pre>

This endpoint is used to get a single EntityList.

**Example**

.. code-block:: bash

      curl -X GET https://api.ona.io/api/v2/entity-lists/1


**Response**

Status: ``200 OK``

Body:

.. code-block:: json

      {
         "id":16,
         "name":"trees",
         "project":"http://testserver/api/v1/projects/13",
         "public":false,
         "date_created":"2024-04-17T11:43:08.530848Z",
         "date_modified":"2024-04-17T11:43:09.030105Z",
         "num_registration_forms":1,
         "num_follow_up_forms":1,
         "num_entities":1,
         "registration_forms":[
            {
               "title":"Trees registration",
               "xform":"http://testserver/api/v1/forms/15",
               "id_string":"trees_registration",
               "save_to":[
                  "geometry",
                  "species",
                  "circumference_cm"
               ]
            }
         ],
         "follow_up_forms":[
            {
               "title":"Trees follow-up",
               "xform":"http://testserver/api/v1/forms/16",
               "id_string":"trees_follow_up"
            }
         ]
      }


Delete EntityList
-----------------
.. raw:: html

	   <pre class="prettyprint"><b>DELETE</b> api/v2/entity-lists/&lt;entity_list_id&gt;</pre>


This endpoint is used to delete a single EntityList dataset.

**Example**

.. code-block:: bash

      curl -X DELETE https://api.ona.io/api/v2/entity-lists/1 \
      -H "Authorization: Token ACCESS_TOKEN"

**Response**

Status: ``204 No Content``

Get a list of Entities
----------------------

.. raw:: html

	   <pre class="prettyprint"><b>GET</b> api/v2/entity-lists/&lt;entity_list_id&gt;/entities</pre>

This endpoint is used to get Entities belonging to a single EntityList dataset.

The maximum number of items returned is ``1000``. To get more results than this, pagination is required. Refer to getting `paginated results <#paginated-entities>`_ section.

**Example**

.. code-block:: bash

      curl -X GET https://api.ona.io/api/v2/entity-lists/1/entities

**Response**

Status: ``200 OK``

Body:

.. code-block:: json

      [
         {
            "url":"http://testserver/api/v2/entity-lists/1/entities/3",
            "id":3,
            "uuid": "dbee4c32-a922-451c-9df7-42f40bf78f48",
            "date_created": "2024-06-20T07:37:20.416054Z",
            "data": {
               "species":"purpleheart",
               "geometry":"-1.286905 36.772845 0 0",
               "circumference_cm":300,
               "label":"300cm purpleheart",
            }
         },
         {
            "url":"http://testserver/api/v2/entity-lists/1/entities/4",
            "id":4,
            "uuid": "517185b4-bc06-450c-a6ce-44605dec5480",
            "date_created": "2024-06-20T07:38:20.416054Z",
            "data": {
               "species":"wallaba",
               "geometry":"-1.305796 36.791849 0 0",
               "intake_notes":"Looks malnourished",
               "circumference_cm":100,
               "label":"100cm wallaba",
            }
         }
      ]

.. _paginated-entities:

Get a paginated list of Entities
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. raw:: html

	   <pre class="prettyprint"><b>GET</b> /api/v2/entity-lists/1/entities?page=&lt;page&gt;&page_size=&lt;page_size&gt;</pre>

Returns a list of projects using page number and the number of items per page. Use the ``page`` parameter to specify page number and ``page_size`` parameter is used to set the custom page size.

- ``page`` - Integer representing the page.
- ``page_size`` - Integer representing the number of records that should be returned in a single page. The maximum number of items that can be requested in a page via the ``page_size`` query param is ``10,000``.

**Example**

.. code-block:: bash

      curl -X GET https://api.ona.io/api/v2/entity-lists/1/entities?page=1&page_size=100

**Response**

Status: ``200 OK``

Body:

.. code-block:: json

      [
         {
            "url":"http://testserver/api/v2/entity-lists/1/entities/3",
            "id":3,
            "uuid": "dbee4c32-a922-451c-9df7-42f40bf78f48",
            "date_created": "2024-06-20T07:37:20.416054Z",
            "data": {
               "species":"purpleheart",
               "geometry":"-1.286905 36.772845 0 0",
               "circumference_cm":300,
               "label":"300cm purpleheart",
            }
         }
      ]


Search a list of Entities
~~~~~~~~~~~~~~~~~~~~~~~~~

.. raw:: html

	   <pre class="prettyprint"><b>GET</b> /api/v2/entity-lists/1/entities?search=&lt;search_term&gt;</pre>

Limit list of Entities to those whose data partially matches the provided search term.

Matches are case insensitive.

**Example**

.. code-block:: bash

      curl -X GET https://api.ona.io/api/v2/entity-lists/1/entities?search=wallaba

**Response**

Status: ``200 OK``

Body:

.. code-block:: json

      [
         {
            "url":"http://testserver/api/v2/entity-lists/1/entities/4",
            "id":4,
            "uuid": "517185b4-bc06-450c-a6ce-44605dec5480",
            "date_created": "2024-06-20T07:38:20.416054Z",
            "data": {
               "species":"wallaba",
               "geometry":"-1.305796 36.791849 0 0",
               "intake_notes":"Looks malnourished",
               "circumference_cm":100,
               "label":"100cm wallaba",
            }
         }
      ]


Get Entity Details
-------------------

.. raw:: html

	   <pre class="prettyprint"><b>GET</b> api/v2/entity-lists/&lt;entity_list_id&gt;/entities/&lt;entity_id&gt;</pre>

This endpoint is used to get a single Entity.

**Example**

.. code-block:: bash

      curl -X GET https://api.ona.io/api/v2/entity-lists/1/entities/3

**Response**

Status: ``200 OK``

Body:

.. code-block:: json

      {
         "id":3,
         "uuid": "dbee4c32-a922-451c-9df7-42f40bf78f48",
         "date_created": "2024-06-20T07:37:20.416054Z",
         "date_modified": "2024-06-20T07:37:20.416054Z",
         "data": {
            "species":"purpleheart",
            "geometry":"-1.286905 36.772845 0 0",
            "circumference_cm":300,
            "label":"300cm purpleheart",
         }
      }


Update Entity
-------------

.. raw:: html

	   <pre class="prettyprint"><b>PATCH</b> api/v2/entity-lists/&lt;entity_list_id&gt;/entities/&lt;entity_id&gt;</pre>

This endpoint is used to update the label or the properties (passed as JSON in the request body) of an Entity.

You only need to include the properties you wish to update. To unset the value of any property, you can set it to empty string ("") or null.

A property must exist in the EntityList dataset.

The label must be a non-empty string.

**Example**

.. code-block:: bash


      curl -X PATCH https://api.ona.io/api/v2/entity-lists/1/entities/1 \
      -H "Authorization: Token ACCESS_TOKEN" \
      -H "Content-Type: application/json" \
      -d '{
            "label": "30cm mora",
            "data": {
                  "geometry": "-1.286805 36.772845 0 0",
                  "species": "mora",
                  "circumference_cm": 30
            }
         }'

**Response**

Status: ``200 OK``

Body:

.. code-block:: json

      {
         "id": 1,
         "uuid": "dbee4c32-a922-451c-9df7-42f40bf78f48",
         "date_created": "2024-06-20T07:37:20.416054Z",
         "date_modified": "2024-06-20T08:37:20.416054Z",
         "data": {
            "geometry": "-1.286805 36.772845 0 0",
            "species": "mora",
            "circumference_cm": 30,
            "label": "30cm mora",
         }
      }

Delete an Entity
----------------

.. raw:: html

	   <pre class="prettyprint"><b>DELETE</b> api/v2/entity-lists/&lt;entity_list_id&gt;/entities/&lt;entity_id&gt;</pre>

The endpoint is used to delete an Entity.

**Example**

.. code-block:: bash

      curl -X DELETE https://api.ona.io/api/v2/entity-lists/1/entities/1 \
      -H "Authorization: Token ACCESS_TOKEN"


**Response**

Status: ``204 No Content``
