Data Lists
**********
   """
This endpoint provides access to submitted data in JSON format. Where:

* `pk` - the form unique identifier
* `dataid` - submission data unique identifier
* `owner` - username of the owner(user/organization) of the data point

## GET JSON List of data end points

Lists the data endpoints accessible to requesting user, for anonymous access
a list of public data endpoints is returned.

<pre class="prettyprint">
<b>GET</b> /api/v1/data
</pre>

> Example
>
>       curl -X GET https://ona.io/api/v1/data

> Response
>
>        [{
>            "id": 4240,
>            "id_string": "dhis2form"
>            "title": "dhis2form"
>            "description": "dhis2form"
>            "url": "https://ona.io/api/v1/data/4240"
>         },
>            ...
>        ]

## GET JSON List of data end points using limit operators

Lists the data endpoints accesible to the requesting user based on 'start'
and/or 'limit' query parameters. Use the start parameter to skip a number
of records and the limit parameter to limit the number of records returned.
<pre class="prettyprint">
<b>GET</b> /api/v1/data/<code>{pk}</code>?<code>start</code>=<code>start_value\
</code>
</pre>
>
>       curl -X GET 'https://ona.io/api/v1/data/2?start=5'

<pre class="prettyprint">
<b>GET</b> /api/v1/data/<code>{pk}</code>?<code>limit</code>=<code>limit_value\
</code>
</pre>
>
>       curl -X GET 'https://ona.io/api/v1/data/2?limit=2'

<pre class="prettyprint">
<b>GET</b> /api/v1/data/<code>{pk}</code>?<code>start</code>=<code>start_value\
</code>&</code><code>limit</code>=<code>limit_value</code>
</pre>
>
>       curl -X GET 'https://ona.io/api/v1/data/2?start=3&limit=4'

## Download data in `csv` format
<pre class="prettyprint">
<b>GET</b> /api/v1/data.csv</pre>
>
>       curl -O https://ona.io/api/v1/data.csv

## GET JSON List of data end points filter by owner

Lists the data endpoints accessible to requesting user, for the specified
`owner` as a query parameter.

<pre class="prettyprint">
<b>GET</b> /api/v1/data?<code>owner</code>=<code>owner_username</code>
</pre>

> Example
>
>       curl -X GET https://ona.io/api/v1/data?owner=ona

## Get Submitted data for a specific form
Provides a list of json submitted data for a specific form.
<pre class="prettyprint">
<b>GET</b> /api/v1/data/<code>{pk}</code></pre>
> Example
>
>       curl -X GET https://ona.io/api/v1/data/22845

> Response
>
>        [
>            {
>                "_id": 4503,
>                "_bamboo_dataset_id": "",
>                "_deleted_at": null,
>                "expense_type": "service",
>                "_xform_id_string": "exp",
>                "_geolocation": [
>                    null,
>                    null
>                ],
>                "end": "2013-01-03T10:26:25.674+03",
>                "start": "2013-01-03T10:25:17.409+03",
>                "expense_date": "2011-12-23",
>                "_status": "submitted_via_web",
>                "today": "2013-01-03",
>                "_uuid": "2e599f6fe0de42d3a1417fb7d821c859",
>                "imei": "351746052013466",
>                "formhub/uuid": "46ea15e2b8134624a47e2c4b77eef0d4",
>                "kind": "monthly",
>                "_submission_time": "2013-01-03T02:27:19",
>                "required": "yes",
>                "_attachments": [],
>                "item": "Rent",
>                "amount": "35000.0",
>                "deviceid": "351746052013466",
>                "subscriberid": "639027...60317"
>            },
>            {
>                ....
>                "subscriberid": "639027...60317"
>            }
>        ]

## Get a single data submission for a given form

Get a single specific submission json data providing `pk`
 and `dataid` as url path parameters, where:

* `pk` - is the identifying number for a specific form
* `dataid` - is the unique id of the data, the value of `_id` or `_uuid`

<pre class="prettyprint">
<b>GET</b> /api/v1/data/<code>{pk}</code>/<code>{dataid}</code></pre>
> Example
>
>       curl -X GET https://ona.io/api/v1/data/22845/4503

> Response
>
>            {
>                "_id": 4503,
>                "_bamboo_dataset_id": "",
>                "_deleted_at": null,
>                "expense_type": "service",
>                "_xform_id_string": "exp",
>                "_geolocation": [
>                    null,
>                    null
>                ],
>                "end": "2013-01-03T10:26:25.674+03",
>                "start": "2013-01-03T10:25:17.409+03",
>                "expense_date": "2011-12-23",
>                "_status": "submitted_via_web",
>                "today": "2013-01-03",
>                "_uuid": "2e599f6fe0de42d3a1417fb7d821c859",
>                "imei": "351746052013466",
>                "formhub/uuid": "46ea15e2b8134624a47e2c4b77eef0d4",
>                "kind": "monthly",
>                "_submission_time": "2013-01-03T02:27:19",
>                "required": "yes",
>                "_attachments": [],
>                "item": "Rent",
>                "amount": "35000.0",
>                "deviceid": "351746052013466",
>                "subscriberid": "639027...60317"
>            },
>            {
>                ....
>                "subscriberid": "639027...60317"
>            }
>        ]

## Query submitted data of a specific form
Provides a list of json submitted data for a specific form. Use `query`
parameter to apply form data specific, see
<a href="http://docs.mongodb.org/manual/reference/operator/query/">
http://docs.mongodb.org/manual/reference/operator/query/</a>.

For more details see
<a href="https://github.com/modilabs/formhub/wiki/Formhub-Access-Points-(API)#
api-parameters">
API Parameters</a>.
<pre class="prettyprint">
<b>GET</b> /api/v1/data/<code>{pk}</code>?query={"field":"value"}</b>
<b>GET</b> /api/v1/data/<code>{pk}</code>?query={"field":{"op": "value"}}"</b>
</pre>
> Example
>
>       curl -X GET 'https://ona.io/api/v1/data/22845?query={"kind": \
"monthly"}'
>       curl -X GET 'https://ona.io/api/v1/data/22845?query={"date": \
{"$gt": "2014-09-29T01:02:03+0000"}}'

> Response
>
>        [
>            {
>                "_id": 4503,
>                "_bamboo_dataset_id": "",
>                "_deleted_at": null,
>                "expense_type": "service",
>                "_xform_id_string": "exp",
>                "_geolocation": [
>                    null,
>                    null
>                ],
>                "end": "2013-01-03T10:26:25.674+03",
>                "start": "2013-01-03T10:25:17.409+03",
>                "expense_date": "2011-12-23",
>                "_status": "submitted_via_web",
>                "today": "2013-01-03",
>                "_uuid": "2e599f6fe0de42d3a1417fb7d821c859",
>                "imei": "351746052013466",
>                "formhub/uuid": "46ea15e2b8134624a47e2c4b77eef0d4",
>                "kind": "monthly",
>                "_submission_time": "2013-01-03T02:27:19",
>                "required": "yes",
>                "_attachments": [],
>                "item": "Rent",
>                "amount": "35000.0",
>                "deviceid": "351746052013466",
>                "subscriberid": "639027...60317"
>            },
>            {
>                ....
>                "subscriberid": "639027...60317"
>            }
>        ]

## Query submitted data of a specific form using Tags
Provides a list of json submitted data for a specific form matching specific
tags. Use the `tags` query parameter to filter the list of forms, `tags`
should be a comma separated list of tags.

<pre class="prettyprint">
<b>GET</b> /api/v1/data?<code>tags</code>=<code>tag1,tag2</code></pre>
<pre class="prettyprint">
<b>GET</b> /api/v1/data/<code>{pk}</code>?<code>tags\
</code>=<code>tag1,tag2</code></pre>

> Example
>
>       curl -X GET https://ona.io/api/v1/data/22845?tags=monthly

## Tag a submission data point

A `POST` payload of parameter `tags` with a comma separated list of tags.

Examples

- `animal fruit denim` - space delimited, no commas
- `animal, fruit denim` - comma delimited

<pre class="prettyprint">
<b>POST</b> /api/v1/data/<code>{pk}</code>/<code>{dataid}</code>/labels</pre>

Payload

    {"tags": "tag1, tag2"}

## Delete a specific tag from a submission

<pre class="prettyprint">
<b>DELETE</b> /api/v1/data/<code>{pk}</code>/<code>\
{dataid}</code>/labels/<code>tag_name</code></pre>

> Request
>
>       curl -X DELETE \
https://ona.io/api/v1/data/28058/20/labels/tag1
or to delete the tag "hello world"
>
>       curl -X DELETE \
https://ona.io/api/v1/data/28058/20/labels/hello%20world
>
> Response
>
>        HTTP 200 OK

## Get list of public data endpoints

<pre class="prettyprint">
<b>GET</b> /api/v1/data/public
</pre>

> Example
>
>       curl -X GET https://ona.io/api/v1/data/public

> Response
>
>        [{
>            "id": 4240,
>            "id_string": "dhis2form"
>            "title": "dhis2form"
>            "description": "dhis2form"
>            "url": "https://ona.io/api/v1/data/4240"
>         },
>            ...
>        ]

## Get enketo edit link for a submission instance

<pre class="prettyprint">
<b>GET</b> /api/v1/data/<code>{pk}</code>/<code>{dataid}</code>/enketo
</pre>

> Example
>
>       curl -X GET https://ona.io/api/v1/data/28058/20/enketo?return_url=url

> Response
>       {"url": "https://hmh2a.enketo.formhub.org"}
>
>

## Delete a specific submission instance

Delete a specific submission in a form

<pre class="prettyprint">
<b>DELETE</b> /api/v1/data/<code>{pk}</code>/<code>{dataid}</code>
</pre>

> Example
>
>       curl -X DELETE https://ona.io/api/v1/data/28058/20

> Response
>
>       HTTP 204 No Content
>
>


## GEOJSON

Get a valid geojson value from the submissions

Options

* `geo_field` - valid field that can be converted to a geojson.
(Point, LineString, Polygon)
* `fields` - additional comma separated values that are to be added to the
properties section

<pre class="prettyprint">
<b>GET</b> /api/v1/data/<code>{pk}</code>/<code>{dataid}</code>.geojson
</pre>

With options
<pre class="prettyprint">
<b>GET</b> /api/v1/data/<code>{pk}</code>/<code>{dataid}</code>.geojson?\
geo_field=<code>{field_name}</code>&fields=<code>{list,of,fields}</code>
</pre>

> Example
>
>       curl -X GET https://ona.io/api/v1/data/28058/20.geojson

> Response
>
>       HTTP 200 OK
> Response
>
>        {
>           "type": "Feature",
>           "geometry":
>               {
>                   "type": "GeometryCollection",
>                    "geometries":
>                       [{
>                           "type": "Point",
>                           "coordinates":
>                               [36.787219, -1.294197]
>                       }]
>               },
>           "properties":
>               {
>                   "id": 6448,
>                    "xform": 65
>               }
>       }
>

List the geojson values

<pre class="prettyprint">
<b>GET</b> /api/v1/data/<code>{pk}</code>.geojson
</pre>

> Example
>
>       curl -X GET https://ona.io/api/v1/data/28058.geojson

> Response
>
>       HTTP 200 OK
> Response
>
>        {
>           "type": "FeatureCollection",
>            "features":
>               [{
>                   "type": "Feature",
>                    "geometry":
>                       {
>                       "type": "GeometryCollection",
>                        "geometries":
>                           [{
>                               "type": "Point",
>                                "coordinates": [36.787219, -1.294197]
>                           }]
>                       },
>                    "properties":
>                       {"id": 6448, "xform": 65}
>               },
>                {
>                    "type": "Feature",
>                     "geometry":
>                        {
>                           "type": "GeometryCollection",
>                            "geometries":
>                               [{
>                                   "type": "Point",
>                                    "coordinates": [36.7872606, -1.2942131]
>                               }]
>                        },
>                      "properties":
>                           {"id": 6447, "xform": 65}
>               }]
>        }

## OSM

The `.osm` file format concatenates all the files for a form or individual
 submission. When the `.json` endpoint is accessed, the individual osm files
 are listed on the `_attachments` key.

### OSM endpoint for all osm files uploaded to a form concatenated.

<pre class="prettyprint">
<b>GET</b> /api/v1/data/<code>{pk}</code>.osm
</pre>

> Example
>
>       curl -X GET https://ona.io/api/v1/data/28058.osm

### OSM endpoint with all osm files for a specific submission concatenated.

<pre class="prettyprint">
<b>GET</b> /api/v1/data/<code>{pk}</code>/<code>{data_id}</code>.osm
</pre>

> Example
>
>       curl -X GET https://ona.io/api/v1/data/28058/20.osm


"""