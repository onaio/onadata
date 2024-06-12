# Entities

Entities allow you to share information between forms, enabling the collection of longitudinal data, management of cases over time, and support for other complex workflows.

The following endpoints provides access to Entities related data: Where:

- `Entity` - Each item that gets managed by an ODK workflow. Entities are automatically created from submissions receieved from a form that contains entity definitions.
- `EntityList` - a dataset that contains Entities of the same type.
- `entity_list_id` - An EntityList's unique identifier
- `entity_id` - An Entity's unique identifier

## Get EntityLists

`GET /api/v2/entity-lists`

This endpoint is used to get all EntityList datasets the user permission to view.

**Request**

`curl -X GET https://api.ona.io/api/v2/entity-lists`

**Response**

Status: `200 OK`

Body:

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

**Request**

`curl -X GET https://api.ona.io/api/v2/entity-lists?project=9`

**Response**

Status: `200 OK`

Body:

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

This endpoint is used to get a single EntityList.

**Request**

`curl -X GET https://api.ona.io/api/v2/entity-lists/1`

**Response**

Status: `200 OK`

Body:

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

This endpoint is used to get Entities belonging to a single EntityList dataset.

**Request**

`curl -X GET https://api.ona.io/api/v2/entity-lists/1/entities`

**Response**

Status: `200 OK`

Body:

```
[
   {
      "id":3,
      "species":"purpleheart",
      "geometry":"-1.286905 36.772845 0 0",
      "circumference_cm":300,
      "meta/entity/label":"300cm purpleheart",
   },
   {
      "id":4,
      "species":"wallaba",
      "geometry":"-1.305796 36.791849 0 0",
      "intake_notes":"Looks malnourished",
      "circumference_cm":100,
      "meta/entity/label":"100cm wallaba",
   }
]
```

## Get a single Entity

`GET api/v2/entity-lists/<entity_list_id>/entities/<entity_id>`

This endpoint is used to get a single Entity.

**Request**

`curl -X GET https://api.ona.io/api/v2/entity-lists/1/entities/3`

**Response**

Status: `200 OK`

Body:

```
{
   "id":3,
   "species":"purpleheart",
   "geometry":"-1.286905 36.772845 0 0",
   "circumference_cm":300,
   "meta/entity/label":"300cm purpleheart",
}
```

## Update Entity

`PATCH api/v2/entity-lists/<entity_list_id>/entities/<entity_id>`

This endpoint is used to update the label or the properties (passed as JSON in the request body) of an Entity.

You only need to include the properties you wish to update. To unset the value of any property, you can set it to empty string ("") or null.

A property must exist in the EntityList dataset.

The label must be a non-empty string.

**Request**

```sh
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
```

**Response**

Status: `200 OK`

Body:

```
{
   "id": 1,
   "geometry": "-1.286805 36.772845 0 0",
   "species": "mora",
   "circumference_cm": 30,
   "meta/entity/label": "30cm mora",
}
```

## Delete an Entity

`DELETE api/v2/entity-lists/<entity_list_id>/entities/<entity_id>`

The endpoint is used to delete an Entity

**Request**

```sh
curl -X DELETE https://api.ona.io/api/v2/entity-lists/1/entities/1 \
-H "Authorization: Token ACCESS_TOKEN"
```

**Response**

Status: `204 No Content`
