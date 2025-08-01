Metadata
********

This endpoint provides access to form metadata, for example, supporting
documents, media files to be used in the form, source documents and map
layers.

- ``pk`` - primary key for the metadata
- ``formid`` - the form id for a form
- ``format`` - is the extension of a file format e.g ``png``, ``csv``

Permissions
-----------

This endpoint applies the same permissions someone has on the form.

Get list of metadata
--------------------

Returns a list of metadata across all forms requesting user has access to.

.. raw:: html

    <pre class="prettyprint">GET /api/v1/metadata</pre>

::

    HTTP 200 OK

    [
        {
            "data_file": "",
            "data_file_type": null,
            "data_type": "public_link",
            "data_value": "http://mylink",
            "id": 406,
            "url": "https://api.ona.io/api/v1/metadata/406",
            "xform": 328
        },
        {
            "data_file": "username/form-media/a.png",
            "data_file_type": "image/png",
            "data_type": "media",
            "data_value": "a.png",
            "id": 7100,
            "url": "https://api.ona.io/api/v1/metadata/7100",
            "xform": 320
        },
        ....
    ]

Get list of metadata for a specific form
-----------------------------------------

The form endpoint, ``/api/v1/forms/formid``, contains a ``metadata`` field
has list of metadata for the form. Alternatively, you can supply the query
parameter ``xform`` with the `formid` as the value.

.. raw:: html

    <pre class="prettyprint">
    GET /api/v1/metadata?<code>xform=formid</code></pre>

::

    HTTP 200 OK

    [
        {
            "data_file": "username/form-media/a.png",
            "data_file_type": "image/png",
            "data_type": "media",
            "data_value": "a.png",
            "id": 7100,
            "url": "https://api.ona.io/api/v1/metadata/7100",
            "xform": 320
        },
        ....
    ]

Get a specific metadata
------------------------
.. raw:: html

    <pre class="prettyprint">
    GET /api/v1/metadata/<code>{pk}</code></pre>

::

    curl -X GET https://api.ona.io/api/v1/metadata/7100

::

    HTTP 200 OK

    {
        "data_file": "username/form-media/a.png",
        "data_file_type": "image/png",
        "data_type": "media",
        "data_value": "a.png",
        "id": 7100,
        "url": "https://api.ona.io/api/v1/metadata/7100",
        "xform": 320
    }


If the metadata is a file, appending the extension of the file type would
return the file itself e.g:

.. raw:: html

    <pre class="prettyprint">
    GET /api/v1/metadata/<code>{pk}.{format}</code></pre>

::

    curl -X GET https://api.ona.io/api/v1/metadata/7100.png -o a.png

Alternatively, if the request is made with an ``Accept`` header of the
content type of the file the file would be returned e.g

.. raw:: html

    <pre class="prettyprint">GET /api/v1/metadata/<code>{pk}</code> Accept: image/png </pre>

::

     curl -X GET https://api.ona.io/api/v1/metadata/7100 -H "Accept: image/png" -o a.png

Add metadata or media file to a form
-------------------------------------
.. raw:: html

    <pre class="prettyprint">POST /api/v1/metadata</pre>

*Payload*
::

           {"xform": <formid>, "data_type": "<data_type>", \
    "data_value": "<data_value>"}

Where:

- ``data_type`` - can be 'media' or 'source' or 'supporting_doc'
- ``data_value`` - can be text or a file name
- ``xform`` - the form id you are adding the media to
- ``data_file`` - optional, should be the file you want to upload

Example:
^^^^^^^^
::

        curl -X POST -d "{"data_type": "mapbox_layer", "data_value":"example||https://api.tiles.mapbox.com/v3/examples.map-0l53fhk2.json||example attribution", "xform": 320}" https://api.ona.io/api/v1/metadata -H "Content-Type: appliction/json"

::

        HTTP 201 CREATED

        {
        "id": 7119,
        "xform": 320,
        "data_value": "example||https://api.tiles.mapbox.com/v3/examples.map-0l53fhk2.json||example attribution",
        "data_type": "mapbox_layer",
        "data_file": null,
        "data_file_type": null,
        "url": "https://api.ona.io/api/v1/metadata/7119.json"
        }

Media upload example:
^^^^^^^^^^^^^^^^^^^^^
::


            curl -X POST -F 'data_type=media' -F 'data_value=demo.jpg' \
    -F 'xform=320' -F "data_file=@folder.jpg" https://api.ona.io/api/v1/metadata.json

::

        HTTP 201 CREATED

        {
        "id": 7121,
        "xform": 320,
        "data_value": "folder.jpg",
        "data_type": "media",
        "data_file": "ukanga/formid-media/folder.jpg",
        "data_file_type": "image/jpeg",
        "url": "https://api.ona.io/api/v1/metadata/7121.json"
        }


Link XForm or Dataview as a media to a form
-------------------------------------------

It is possible to link another form or a dataview as a csv media resource to a form,
the linked form will be downloadable by ODK Collect and Enketo as media. The ``data_type`` parameter
will be 'media'm the ``xform`` parameter will be the form id you are adding the
media to and the ``data_value`` param is a string of the form
`"xform [form id] [filename]"` or `"dataview [dataview id] [filename]"`.

Where:

- ``[form id]`` - is the numeric id of the form
- ``[dataview id]`` - is the numeric id of the dataview
- ``[filename]`` - name of file for the linked resource, e.g `fruits` -> `fruits.csv`


Link XForm or Dataview as a media example:
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::


        curl -X POST -F 'data_type=media' -F 'xform=320' -F 'data_value="xform 328 places"' https://api.ona.io/api/v1/metadata.json

::

        HTTP 201 CREATED

        {
        "id": 7121,
        "xform": 320,
        "data_value": "xform 328 places",
        "data_type": "media",
        "url": "https://api.ona.io/api/v1/metadata/7121.json"
        }


Link XForm as a GeoJSON media attachment example:
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::


        curl -X POST -F 'data_type=media' -F 'xform=320' -F 'data_value="xform_geojson 328 places"' -F 'extra_data='{"data_title": "fruits", "data_simple_style": true, "data_geo_field": "geofied_1", "data_fields": "field_1,field_2"}'' https://api.ona.io/api/v1/metadata.json

::

        HTTP 201 CREATED

        {
        "id": 7121,
        "xform": 320,
        "data_value": "xform_geojson 328 places",
        "data_type": "media",
        "extra_data": '{"data_title": "fruits", "data_simple_style": true, "data_geo_field": "geofied_1", "data_fields": "field_1,field_2"}'
        "url": "https://api.ona.io/api/v1/metadata/7121.json"
        }

Create XForm meta permissions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Set meta permissions for a specific form by passing two roles that are pipe delimited.
First role indicates editor default role, the second is the dataentry default role and the last is the readonly default role.

Example
::


        curl -X POST -F 'data_type=xform_meta_perms' -F 'xform=320' -F 'data_value="editor-minor|dataentryonly|readonly-no-download"' https://api.ona.io/api/v1/metadata.json

::

        HTTP 201 CREATED


Delete Metadata
^^^^^^^^^^^^^^^^
.. raw:: html

    <pre class="prettyprint">DELETE /api/v1/metadata/<code>{pk}</code></pre>
