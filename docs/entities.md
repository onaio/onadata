# Entities

Entities allow you to share information between forms, enabling the collection of longitudinal data, management of cases over time, and support for other complex workflows.

The following endpoints provides access to Entities related data: Where:

- `Entity` - Each item that gets managed by an ODK workflow. Entities are automatically created from submissions receieved from a form that contains entity definitions.
- `EntityList` - a dataset that contains Entities of the same type.
- `entity_list_id` - An EntityList's unique identifier
- `entity_id` - An Entity's unique identifier

## Create EntityList

`POST /api/v2/entity-lists`

This endpoint is used to create a single EntityList dataset within a project. Entities for the dataset can then be created from a form or via the API.

EntityList name must not include `.` or start with `__`.

EntityList name is unique per project.

The EntityList by default has no properties.

**Request**

```sh
curl -X POST "https://api.ona.io/api/v2/entity-lists" \
     -H "Authorization: Token ACCESS_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
            "name": "trees",
            "project": "2",
         }'
```

**Response**

Staus: `201 Created`

Body:

```
{
   "id":1,
   "name":"trees",
   "project":2,
   "date_created":"2024-06-27T07:35:53.451077Z",
   "date_modified":"2024-06-27T07:35:53.451091Z"
}
```

## Get a list of EntityLists

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

### Get a list of Entities for a specific project

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

### Get a paginated list of EntityLists

`GET /api/v2/entity-lists?page=<page>&page_size=<page_size>`

Returns a list of projects using page number and the number of items per page. Use the `page` parameter to specify page number and `page_size` parameter is used to set the custom page size.

- `page` - Integer representing the page.
- `page_size` - Integer representing the number of records that should be returned in a single page. The maximum number of items that can be requested in a page via the `page_size` query param is `10,000`

**Request**

`curl -X GET https://api.ona.io/api/v2/entity-lists?page=1&page_size=100`

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

    ...
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

## Delete EntityList

`DELETE api/v2/entity-lists/<entity_list_id>`

This endpoint is used to delete a single EntityList dataset

**Request**

```sh
curl -X DELETE https://api.ona.io/api/v2/entity-lists/1 \
-H "Authorization: Token ACCESS_TOKEN"
```

**Response**

Status: `204 No Content`

## Get a list of Entities

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
```

### Get a paginated list of Entities

`GET /api/v2/entity-lists/1/entities?page=<page>&page_size=<page_size>`

Returns a list of projects using page number and the number of items per page. Use the `page` parameter to specify page number and `page_size` parameter is used to set the custom page size.

- `page` - Integer representing the page.
- `page_size` - Integer representing the number of records that should be returned in a single page. The maximum number of items that can be requested in a page via the `page_size` query param is `10,000`

**Request**

`curl -X GET https://api.ona.io/api/v2/entity-lists/1/entities?page=1&page_size=100`

**Response**

Status: `200 OK`

Body:

```
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
   ...
]
```

### Search a list of Entities

`GET /api/v2/entity-lists/1/entities?search=<search_term>`

Limit list of Entities to those whose metadata or data partially match the provided search term.

Matches are case insensitive.

**Request**

`curl -X GET https://api.ona.io/api/v2/entity-lists/1/entities?search=wallaba`

**Response**

Status: `200 OK`

Body:

```
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
   "uuid": "dbee4c32-a922-451c-9df7-42f40bf78f48",
   "date_created": "2024-06-20T07:37:20.416054Z",
   "date_modified: "2024-06-20T07:37:20.416054Z",
   "data": {
      "species":"purpleheart",
      "geometry":"-1.286905 36.772845 0 0",
      "circumference_cm":300,
      "label":"300cm purpleheart",
   }
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
   "uuid": "dbee4c32-a922-451c-9df7-42f40bf78f48",
   "date_created": "2024-06-20T07:37:20.416054Z",
   "date_modified: "2024-06-20T08:37:20.416054Z",
   "data": {
      "geometry": "-1.286805 36.772845 0 0",
      "species": "mora",
      "circumference_cm": 30,
      "label": "30cm mora",
   }
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
