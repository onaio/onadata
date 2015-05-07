
Attachements and Media
**********************

Lists attachments of all xforms
--------------------------------
::

	GET /api/v1/media/


Example
^^^^^^^
::

       curl -X GET https://ona.io/api/v1/media

Response
^^^^^^^^
::

    [
        {
            "download_url": "http://ona.io/api/v1/media/1.jpg",
            "small_download_url": "http://ona.io/api/v1/media/1-small.jpg",
            "medium_download_url": "http://ona.io/api/v1/media/1-medium.jpg",
            "filename": "doe/attachments/1408520136827.jpg",
            "id": 1,
            "instance": 1,
            "mimetype": "image/jpeg",
            "url": "http://ona.io/api/v1/media/1",
            "xform": 1,
        },
        ...
    ]

Paginate attachment
-------------------------------------------
Returns a list of attachments using page number and the number of items per page. Use the ``page`` parameter to specify page number and ``page_size`` parameter is used to set the custom page size.

Example
^^^^^^^^
::
  
      curl -X GET https://ona.io/api/v1/media.json?page=1&page_size=4

Retrieve details of an attachment
---------------------------------
.. raw:: html

    <pre class="prettyprint">  GET /api/v1/media/<code>{pk}</code></pre>
    
Example
^^^^^^^
::

      curl -X GET https://ona.io/api/v1/media/1

Response
^^^^^^^^^

::

    {
        "download_url": "http://ona.io/api/v1/media/1.jpg",
        "small_download_url": "http://ona.io/api/v1/media/1-small.jpg",
        "medium_download_url": "http://ona.io/api/v1/media/1-medium.jpg",
        "filename": "doe/attachments/1408520136827.jpg",
        "id": 1,
        "instance": 1,
        "mimetype": "image/jpeg",
        "url": "http://ona.io/api/v1/media/1",
        "xform": 1,
    }

Retrieve an attachment file
----------------------------

.. raw:: html

    <pre class="prettyprint">GET /api/v1/media/<code>{pk}.{format}</code></pre>
    
::

    curl -X GET https://ona.io/api/v1/media/1.png -o a.png

Alternatively, if the request is made with an `Accept` header of the
content type of the file the file would be returned e.g

.. raw:: html

    <pre class="prettyprint">GET /api/v1/media/<code>{pk}</code> Accept: image/png </pre>
    
Example
^^^^^^^^

::

    curl -X GET https://ona.io/api/v1/media/1 -H "Accept: image/png" -o a.png

Lists attachments of a specific xform
--------------------------------------

.. raw:: html

    <pre class="prettyprint">GET /api/v1/media/?xform=<code>{xform}</code></pre>
    
Example
^^^^^^^^
::

     curl -X GET https://ona.io/api/v1/media?xform=1

Response
^^^^^^^^
::

    [
        {
            "download_url": "http://ona.io/api/v1/media/1.jpg",
            "small_download_url": "http://ona.io/api/v1/media/1-small.jpg",
            "medium_download_url": "http://ona.io/api/v1/media/1-medium.jpg",
            "filename": "doe/attachments/1408520136827.jpg",
            "id": 1,
            "instance": 1,
            "mimetype": "image/jpeg",
            "url": "http://ona.io/api/v1/media/1",
            "xform": 1,
        },
        ...
    ]

Lists attachments of a specific instance
------------------------------------------

.. raw:: html

    <pre class="prettyprint">GET /api/v1/media?instance=<code>{instance}</code></pre>
 

Example
^^^^^^^^

::

     curl -X GET https://ona.io/api/v1/media?instance=1

Response
^^^^^^^^^
::


    [
        {
            "download_url": "http://ona.io/api/v1/media/1.jpg",
            "small_download_url": "http://ona.io/api/v1/media/1-small.jpg",
            "medium_download_url": "http://ona.io/api/v1/media/1-medium.jpg",
            "filename": "doe/attachments/1408520136827.jpg",
            "id": 1,
            "instance": 1,
            "mimetype": "image/jpeg",
            "url": "http://ona.io/api/v1/media/1",
            "xform": 1,
        },
        ...
    ]

Retrieve image link of an attachment
------------------------------------

.. raw:: html

    <pre class="prettyprint">GET /api/v1/media/<code>{pk}</code></pre>
    
Example
^^^^^^^
::


    curl -X GET https://ona.io/api/v1/media/1\?filename=doe/attachments/1408520136827.jpg

Response
^^^^^^^^^
::

        http://ona.io/api/v1/media/1.jpg

    
