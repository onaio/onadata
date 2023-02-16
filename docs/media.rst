
Attachments and Media
*********************

Lists attachments of all xforms
-------------------------------
::

	GET /api/v1/media/


Example
^^^^^^^
::

       curl -X GET https://api.ona.io/api/v1/media

Response
^^^^^^^^
::

    [
        {
            "download_url": "http://api.ona.io/api/v1/media/1.jpg",
            "small_download_url": "http://api.ona.io/api/v1/media/1-small.jpg",
            "medium_download_url": "http://api.ona.io/api/v1/media/1-medium.jpg",
            "filename": "doe/attachments/1408520136827.jpg",
            "id": 1,
            "instance": 1,
            "mimetype": "image/jpeg",
            "url": "http://api.ona.io/api/v1/media/1",
            "xform": 1,
        },
        ...
    ]

Paginate attachment
-------------------
Returns a list of attachments using page number and the number of items per page. Use the ``page`` parameter to specify page number and ``page_size`` parameter is used to set the custom page size.

Example
^^^^^^^
::
  
      curl -X GET https://api.ona.io/api/v1/media.json?page=1&page_size=4

Retrieve details of an attachment
---------------------------------
.. raw:: html

    <pre class="prettyprint">  GET /api/v1/media/<code>{pk}</code></pre>
    
Example
^^^^^^^
::

      curl -X GET https://api.ona.io/api/v1/media/1

Response
^^^^^^^^

::

    {
        "download_url": "http://api.ona.io/api/v1/media/1.jpg",
        "small_download_url": "http://api.ona.io/api/v1/media/1-small.jpg",
        "medium_download_url": "http://api.ona.io/api/v1/media/1-medium.jpg",
        "filename": "doe/attachments/1408520136827.jpg",
        "id": 1,
        "instance": 1,
        "mimetype": "image/jpeg",
        "url": "http://api.ona.io/api/v1/media/1",
        "xform": 1,
    }

Retrieve an attachment file
---------------------------

.. raw:: html

    <pre class="prettyprint">GET /api/v1/media/<code>{pk}.{format}</code></pre>
    
::

    curl -X GET https://api.ona.io/api/v1/media/1.png -o a.png

Alternatively, if the request is made with an `Accept` header of the
content type of the file the file would be returned e.g

.. raw:: html

    <pre class="prettyprint">GET /api/v1/media/<code>{pk}</code> Accept: image/png </pre>
    
Example
^^^^^^^

::

    curl -X GET https://api.ona.io/api/v1/media/1 -H "Accept: image/png" -o a.png

Lists attachments of a specific xform
-------------------------------------

.. raw:: html

    <pre class="prettyprint">GET /api/v1/media/?xform=<code>{xform}</code></pre>
    
Example
^^^^^^^
::

     curl -X GET https://api.ona.io/api/v1/media?xform=1

Response
^^^^^^^^
::

    [
        {
            "download_url": "http://api.ona.io/api/v1/media/1.jpg",
            "small_download_url": "http://api.ona.io/api/v1/media/1-small.jpg",
            "medium_download_url": "http://api.ona.io/api/v1/media/1-medium.jpg",
            "filename": "doe/attachments/1408520136827.jpg",
            "id": 1,
            "instance": 1,
            "mimetype": "image/jpeg",
            "url": "http://api.ona.io/api/v1/media/1",
            "xform": 1,
        },
        ...
    ]

Lists attachments of a merged dataset
-------------------------------------

.. raw:: html

    <pre class="prettyprint">GET /api/v1/media/?merged_xform=<code>{merged_xform_id}</code></pre>

Example
^^^^^^^
::

     curl -X GET https://api.ona.io/api/v1/media?merged_xform=1

Response
^^^^^^^^
::

    [
        {
            "url": "http://testserver/api/v1/media/1",
            "filename": "bob/attachments/1_a/test-image_qdCeDHO.png",
            "mimetype": "image/png",
            "field_xpath": null,
            "id": 1,
            "xform": 1,
            "instance": 1,
            "download_url": "http://testserver/api/v1/files/1?filename=bob/attachments/1_a/test-image_qdCeDHO.png",
            "small_download_url": "http://testserver/api/v1/files/1?filename=bob/attachments/1_a/test-image_qdCeDHO.png&suffix=small",
            "medium_download_url": "http://testserver/api/v1/files/1?filename=bob/attachments/1_a/test-image_qdCeDHO.png&suffix=medium"
        },
        ...
    ]

Lists attachments of a filtered dataset
---------------------------------------

You'll ned to pass a `dataview` parameter to the media endpoint. Filtered datasets are internally known as dataviews.

.. raw:: html

    <pre class="prettyprint">GET /api/v1/media/?dataview=<code>{filtered_dataset_id}</code></pre>

Example
^^^^^^^
::

     curl -X GET https://api.ona.io/api/v1/media?dataview=1

Response
^^^^^^^^
::

    [
        {
            "url": "http://testserver/api/v1/media/1",
            "filename": "bob/attachments/1_a/test-image_qdCeDHO.png",
            "mimetype": "image/png",
            "field_xpath": null,
            "id": 1,
            "xform": 1,
            "instance": 1,
            "download_url": "http://testserver/api/v1/files/1?filename=bob/attachments/1_a/test-image_qdCeDHO.png",
            "small_download_url": "http://testserver/api/v1/files/1?filename=bob/attachments/1_a/test-image_qdCeDHO.png&suffix=small",
            "medium_download_url": "http://testserver/api/v1/files/1?filename=bob/attachments/1_a/test-image_qdCeDHO.png&suffix=medium"
        },
        ...
    ]

Lists attachments of a specific instance
----------------------------------------

.. raw:: html

    <pre class="prettyprint">GET /api/v1/media?instance=<code>{instance}</code></pre>
 

Example
^^^^^^^

::

     curl -X GET https://api.ona.io/api/v1/media?instance=1

Response
^^^^^^^^
::


    [
        {
            "download_url": "http://api.ona.io/api/v1/media/1.jpg",
            "small_download_url": "http://api.ona.io/api/v1/media/1-small.jpg",
            "medium_download_url": "http://api.ona.io/api/v1/media/1-medium.jpg",
            "filename": "doe/attachments/1408520136827.jpg",
            "id": 1,
            "instance": 1,
            "mimetype": "image/jpeg",
            "url": "http://api.ona.io/api/v1/media/1",
            "xform": 1,
        },
        ...
    ]

Lists of attachment filter by attachment type
---------------------------------------------
.. raw:: html

    <pre class="prettyprint">GET /api/v1/media?xform=<code>{xform_id}</code>&?type=<code>{attachment_type}</code></pre>

You can use this to get attachment specific to the attachment type.

Example
^^^^^^^
::


    curl -X GET https://api.ona.io/api/v1/media?type=image

Response
^^^^^^^^
::


    [
        {
        "url": "https://api.ona.io/api/v1/media/1",
        "filename": "doe/attachments/4266445458362.png",
        "mimetype": "image/png",
        "field_xpath": null,
        "id": 1,
        "xform": 1,
        "instance": 1,
        "download_url": "http://api.ona.io/api/v1/media/1.png",
        "small_download_url": "http://api.ona.io/api/v1/media/1-small.png",
        "medium_download_url": "http://api.ona.io/api/v1/media/1-medium.png",
        },
        ...
    ]

Supported media attachment types that could be used to filter include:

- video
- audio
- file

Retrieve image link of an attachment
------------------------------------

.. raw:: html

    <pre class="prettyprint">GET /api/v1/media/<code>{pk}</code></pre>
    
Example
^^^^^^^
::


    curl -X GET https://api.ona.io/api/v1/media/1\?filename=doe/attachments/1408520136827.jpg

Response
^^^^^^^^
::

        http://api.ona.io/api/v1/media/1.jpg

Retrieve attachment count for a form
------------------------------------
Returns the total number of attachments for a form

.. raw:: html

    <pre class="prettyprint">GET /api/v1/media/count?xform=<code>{xform_id}</code></pre>

Example
^^^^^^^
::


    curl -X GET https://api.ona.io/api/v1/media/count?xform=1

Response
^^^^^^^^
::


        {"count": 1}
