Onadata-Tableau
***************

Visualize data collected with the onadata application on |Tableau|. This endpoint provides access to submitted data being pushed to Tableau via the Web Data Connector in JSON format.

.. |Tableau| raw:: html

    <a href="https://www.tableau.com/"
    target="_blank">Tableau</a>


Where:

- ``uuid`` - the form open data unique identifier


Tableau Web Data Connector Endpoints
------------------------------------

Schema Endpoint Example
^^^^^^^^^^^^^^^^^^^^^^^
::

    curl -X GET /api/v1/open-data-v2/24fde84caec342a19a7f2e3ea0c36e3f/schema

Response
^^^^^^^^
::

    [
        {
            "table_alias": "data",
            "connection_name": "22_test",
            "column_headers": [
                {
                    "id": "_id",
                    "dataType": "int",
                    "alias": "_id"
                },
                {
                    "id": "country",
                    "dataType": "string",
                    "alias": "country"
                },
                {
                    "id": "note",
                    "dataType": "string",
                    "alias": "note"
                },
                {
                    "id": "user_select",
                    "dataType": "string",
                    "alias": "user_select"
                },
                {
                    "id": "photo",
                    "dataType": "string",
                    "alias": "photo"
                },
                {
                    "id": "meta_instanceID",
                    "dataType": "string",
                    "alias": "meta_instanceID"
                }
            ]
        }
    ]

Forms with nested repeats will generate multiple table schemas for Tableau

Response
^^^^^^^^
::

    [
        {
            "table_alias": "data",
            "connection_name": "22_transportation_new_form",
            "column_headers": [
                {
                    "id": "_id",
                    "dataType": "int",
                    "alias": "_id"
                },
                {
                    "id": "hospital_name",
                    "dataType": "string",
                    "alias": "hospital_name"
                },
                {
                    "id": "hospital_hiv_medication_food_cake",
                    "dataType": "string",
                    "alias": "hospital_hiv_medication_food_cake"
                },
                {
                    "id": "hospital_hiv_medication_food_cheese",
                    "dataType": "string",
                    "alias": "hospital_hiv_medication_food_cheese"
                },
                {
                    "id": "hospital_hiv_medication_food_ham",
                    "dataType": "string",
                    "alias": "hospital_hiv_medication_food_ham"
                },
                {
                    "id": "hospital_hiv_medication_food_vegetables",
                    "dataType": "string",
                    "alias": "hospital_hiv_medication_food_vegetables"
                },
                {
                    "id": "hospital_hiv_medication_have_hiv_medication",
                    "dataType": "string",
                    "alias": "hospital_hiv_medication_have_hiv_medication"
                },
                {
                    "id": "hospital_hiv_medication__gps_latitude",
                    "dataType": "string",
                    "alias": "hospital_hiv_medication__gps_latitude"
                },
                {
                    "id": "hospital_hiv_medication__gps_longitude",
                    "dataType": "string",
                    "alias": "hospital_hiv_medication__gps_longitude"
                },
                {
                    "id": "hospital_hiv_medication__gps_altitude",
                    "dataType": "string",
                    "alias": "hospital_hiv_medication__gps_altitude"
                },
                {
                    "id": "hospital_hiv_medication__gps_precision",
                    "dataType": "string",
                    "alias": "hospital_hiv_medication__gps_precision"
                },
                {
                    "id": "meta_instanceID",
                    "dataType": "string",
                    "alias": "meta_instanceID"
                }
            ]
        },
        {
            "table_alias": "person_repeat",
            "connection_name": "22_transportation_new_form_person_repeat",
            "column_headers": [
                {
                    "id": "_id",
                    "dataType": "int",
                    "alias": "_id"
                },
                {
                    "id": "__parent_id",
                    "dataType": "int",
                    "alias": "__parent_id"
                },
                {
                    "id": "__parent_table",
                    "dataType": "string",
                    "alias": "__parent_table"
                },
                {
                    "id": "hospital_hiv_medication_person_first_name",
                    "dataType": "string",
                    "alias": "hospital_hiv_medication_person_first_name"
                },
                {
                    "id": "hospital_hiv_medication_person_last_name",
                    "dataType": "string",
                    "alias": "hospital_hiv_medication_person_last_name"
                },
                {
                    "id": "hospital_hiv_medication_person_food_cake",
                    "dataType": "string",
                    "alias": "hospital_hiv_medication_person_food_cake"
                },
                {
                    "id": "hospital_hiv_medication_person_food_cheese",
                    "dataType": "string",
                    "alias": "hospital_hiv_medication_person_food_cheese"
                },
                {
                    "id": "hospital_hiv_medication_person_food_ham",
                    "dataType": "string",
                    "alias": "hospital_hiv_medication_person_food_ham"
                },
                {
                    "id": "hospital_hiv_medication_person_food_vegetables",
                    "dataType": "string",
                    "alias": "hospital_hiv_medication_person_food_vegetables"
                },
                {
                    "id": "hospital_hiv_medication_person_have_hiv_medication",
                    "dataType": "string",
                    "alias": "hospital_hiv_medication_person_have_hiv_medication"
                },
                {
                    "id": "hospital_hiv_medication_person_age",
                    "dataType": "int",
                    "alias": "hospital_hiv_medication_person_age"
                },
                {
                    "id": "hospital_hiv_medication_person__gps_latitude",
                    "dataType": "string",
                    "alias": "hospital_hiv_medication_person__gps_latitude"
                },
                {
                    "id": "hospital_hiv_medication_person__gps_longitude",
                    "dataType": "string",
                    "alias": "hospital_hiv_medication_person__gps_longitude"
                },
                {
                    "id": "hospital_hiv_medication_person__gps_altitude",
                    "dataType": "string",
                    "alias": "hospital_hiv_medication_person__gps_altitude"
                },
                {
                    "id": "hospital_hiv_medication_person__gps_precision",
                    "dataType": "string",
                    "alias": "hospital_hiv_medication_person__gps_precision"
                }
            ]
        }
    ]


Data Endpoint Example
^^^^^^^^^^^^^^^^^^^^^
::

       curl -X GET /api/v1/open-data-v2/5d3da685cbe64fc6b97a1b03ffccd847/data

Response
^^^^^^^^
::

    [
        {
            "_id": 4,
            "hospital_name": "Melkizedek",
            "meta_instanceID": "uuid:f0be8145-b840-4fde-a531-a38aeb1260f4",
            "hospital_hiv_medication__gps_latitude": "-1.302025",
            "hospital_hiv_medication__gps_longitude": "36.745877",
            "hospital_hiv_medication__gps_altitude": "0",
            "hospital_hiv_medication__gps_precision": "0",
            "hospital_hiv_medication_food_cake": "TRUE",
            "hospital_hiv_medication_food_cheese": "TRUE",
            "hospital_hiv_medication_food_ham": "TRUE",
            "hospital_hiv_medication_food_vegetables": "TRUE",
            "person_repeat": [
            {
                "__parent_id": 4,
                "__parent_table": "data",
                "_id": 16,
                "hospital_hiv_medication_person_age": 43,
                "hospital_hiv_medication_person__gps_latitude": "-1.302819",
                "hospital_hiv_medication_person__gps_longitude": "36.746857",
                "hospital_hiv_medication_person__gps_altitude": "0",
                "hospital_hiv_medication_person__gps_precision": "0",
                "hospital_hiv_medication_person_food_cake": "TRUE",
                "hospital_hiv_medication_person_food_cheese": "TRUE",
                "hospital_hiv_medication_person_food_ham": "TRUE",
                "hospital_hiv_medication_person_food_vegetables": "TRUE",
                "hospital_hiv_medication_person_last_name": "Kendrik",
                "hospital_hiv_medication_person_first_name": "Tom",
                "hospital_hiv_medication_person_have_hiv_medication": "no"
            }
            ],
            "hospital_hiv_medication_have_hiv_medication": "yes"
        }
    ]
