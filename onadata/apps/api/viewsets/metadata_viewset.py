from rest_framework import renderers
from rest_framework import viewsets
from rest_framework.response import Response

from onadata.apps.api.permissions import MetaDataObjectPermissions
from onadata.apps.api.tools import get_media_file_response
from onadata.apps.main.models.meta_data import MetaData
from onadata.libs.serializers.metadata_serializer import MetaDataSerializer
from onadata.libs import filters
from onadata.libs.renderers.renderers import MediaFileContentNegotiation, \
    MediaFileRenderer


class MetaDataViewSet(viewsets.ModelViewSet):
    """
    This endpoint provides access to form metadata, for example, supporting
    documents, media files to be used in the form, source documents and map
    layers.

    - `pk` - primary key for the metadata
    - `formid` - the form id for a form
    - `format` - is the extension of a file format e.g `png`, `csv`

    ### Permissions

    This endpoint applys the same permissions someone has on the form.

    ## Get list of metadata

    Returns a list of metadata accross all forms requesting user has access to.

    <pre class="prettyprint">GET /api/v1/metadata</pre>

        HTTP 200 OK

        [
            {
                "data_file": "",
                "data_file_type": null,
                "data_type": "public_link",
                "data_value": "http://mylink",
                "id": 406,
                "url": "https://example.com/api/v1/metadata/406",
                "xform": 328
            },
            {
                "data_file": "username/form-media/a.png",
                "data_file_type": "image/png",
                "data_type": "media",
                "data_value": "a.png",
                "id": 7100,
                "url": "https://example.com/api/v1/metadata/7100",
                "xform": 320
            },
            ....
        ]

    ## Get list of metadata for a specific form

    The form endpoint, `/api/v1/forms/formid`, contains a `metadata` field
    has list of metadata for the form. Alternatively, you can supply the query
    parameter `xform` with the `formid` as the value.

    <pre class="prettyprint">
    GET /api/v1/metdata?<code>xform=formid</code></pre>

        HTTP 200 OK

        [
            {
                "data_file": "username/form-media/a.png",
                "data_file_type": "image/png",
                "data_type": "media",
                "data_value": "a.png",
                "id": 7100,
                "url": "https://example.com/api/v1/metadata/7100",
                "xform": 320
            },
            ....
        ]

    ## Get a specific metadata

    <pre class="prettyprint">
    GET /api/v1/metadata/<code>{pk}</code></pre>

        curl -X GET https://example.com/api/v1/metadata/7100

        HTTP 200 OK

        {
            "data_file": "username/form-media/a.png",
            "data_file_type": "image/png",
            "data_type": "media",
            "data_value": "a.png",
            "id": 7100,
            "url": "https://example.com/api/v1/metadata/7100",
            "xform": 320
        }

    If the metadata is a file, appending the extension of the file type would
    return the file itself e.g:

    <pre class="prettyprint">
    GET /api/v1/metadata/<code>{pk}.{format}</code></pre>

        curl -X GET https://example.com/api/v1/metadata/7100.png -o a.png

    Alternatively, if the request is made with an `Accept` header of the
    content type of the file the file would be returned e.g

    <pre class="prettyprint">GET /api/v1/metadata/<code>{pk}</code> \
Accept: image/png </pre>

         curl -X GET https://example.com/api/v1/metadata/7100 \
-H "Accept: image/png" -o a.png

    ## Add metadata or media file to a form

    <pre class="prettyprint">POST /api/v1/metadata</pre>
    Payload

           {"xform": <formid>, "data_type": "<data_type>", \
"data_value": "<data_value>"}

    Where:

    - `data_type` - can be 'media' or 'source' or 'supporting_doc'
    - `data_value` - can be text or a file name
    - `xform` - the form id you are adding the media to
    - `data_file` - optional, should be the file you want to upload

    Example:

            curl -X POST -d "{"data_type": "mapbox_layer", "data_value": \
"example||https://api.tiles.mapbox.com/v3/examples.map-0l53fhk2.json||example\
 attribution", "xform": 320}" https://example.com/api/v1/metadata \
-H "Content-Type: appliction/json"

            HTTP 201 CREATED

            {
            "id": 7119,
            "xform": 320,
            "data_value": "example||https://api.tiles.mapbox.com/v3/examples\
.map-0l53fhk2.json||example attribution",
            "data_type": "mapbox_layer",
            "data_file": null,
            "data_file_type": null,
            "url": "https://example.com/api/v1/metadata/7119.json"
            }

    Media upload example:

            curl -X POST -F 'data_type=media' -F 'data_value=demo.jpg' \
-F 'xform=320' -F "data_file=@folder.jpg" https://example.com/api/v1/metadata.json

            HTTP 201 CREATED

            {
            "id": 7121,
            "xform": 320,
            "data_value": "folder.jpg",
            "data_type": "media",
            "data_file": "ukanga/formid-media/folder.jpg",
            "data_file_type": "image/jpeg",
            "url": "https://example.com/api/v1/metadata/7121.json"
            }


    ## Delete Metadata

    <pre class="prettyprint">DELETE /api/v1/metadata/<code>{pk}</code></pre>

    """
    content_negotiation_class = MediaFileContentNegotiation
    filter_backends = (filters.MetaDataFilter,)
    queryset = MetaData.objects.all()
    permission_classes = (MetaDataObjectPermissions,)
    renderer_classes = (
        renderers.JSONRenderer,
        renderers.BrowsableAPIRenderer,
        MediaFileRenderer)
    serializer_class = MetaDataSerializer

    def retrieve(self, request, *args, **kwargs):
        self.object = self.get_object()

        if isinstance(request.accepted_renderer, MediaFileRenderer) \
                and self.object.data_file is not None:

            return get_media_file_response(self.object)

        serializer = self.get_serializer(self.object)

        return Response(serializer.data)
