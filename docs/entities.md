# Entities

Entities allow you to share information between forms, enabling the collection of longitudinal data, management of cases over time, and support for other complex workflows.

The following endpoints provides access to Entities related data: Where:

- _Entity_ - Each item that gets managed by an ODK workflow. Entities are automatically created from submissions receieved from a form that contains entity definitions.
- _EntityList_ - a dataset that contains Entities of the same type.

## Get EntityLists

`GET /api/v2/entity-lists`

**Example**

`curl -X GET https://api.ona.io/api/v2/entity-lists`

**Response**

```
[
    {
        "url":"http://testserver/api/v2/entity-lists/9",
        "id":9,
        "name":"trees",
        "project":"http://testserver/api/v1/projects/9",
        "public":false,
        "date_created":"2024-04-17T11:26:24.630117Z",
        "date_modified":"2024-04-17T11:26:25.050823Z",
        "num_registration_forms":1,
        "num_follow_up_forms":1,
        "num_entities":1
    }
]

```

To get EntityLists for a specific project

`GET /api/v2/entity-lists?project=<project_id>`

**Example**

`curl -X GET https://api.ona.io/api/v2/entity-lists?project=9`

**Response**

```
[
    {
        "url":"http://testserver/api/v2/entity-lists/9",
        "id":9,
        "name":"trees",
        "project":"http://testserver/api/v1/projects/9",
        "public":false,
        "date_created":"2024-04-17T11:26:24.630117Z",
        "date_modified":"2024-04-17T11:26:25.050823Z",
        "num_registration_forms":1,
        "num_follow_up_forms":1,
        "num_entities":1
    }
]

```

## Get a single EntityList

`GET /api/v2/entity-lists/<entity_list_id>`

**Example**

`curl -X GET https://api.ona.io/api/v2/entity-lists/1`

**Response**

```
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
```

## Get Entities

`GET api/v2/entity-lists/<entity_list_id>/entities`

**Example**

`curl -X GET https://api.ona.io/api/v2/entity-lists/1/entities`

**Response**

```
[
   {
      "_id":3,
      "species":"purpleheart",
      "_version":"2022110901",
      "geometry":"-1.286905 36.772845 0 0",
      "formhub/uuid":"d156a2dce4c34751af57f21ef5c4e6cc",
      "meta/instanceID":"uuid:9d3f042e-cfec-4d2a-8b5b-212e3b04802b",
      "_xform_id_string":"trees_registration",
      "circumference_cm":300,
      "meta/entity/label":"300cm purpleheart",
      "meta/instanceName":"300cm purpleheart"
   },
   {
      "_id":4,
      "species":"wallaba",
      "_version":"2022110901",
      "geometry":"-1.305796 36.791849 0 0",
      "formhub/uuid":"d156a2dce4c34751af57f21ef5c4e6cc",
      "intake_notes":"Looks malnourished",
      "meta/instanceID":"uuid:648e4106-2224-4bd7-8bf9-859102fc6fae",
      "_xform_id_string":"trees_registration",
      "circumference_cm":100,
      "meta/entity/label":"100cm wallaba",
      "meta/instanceName":"100cm wallaba"
   }
]
```
