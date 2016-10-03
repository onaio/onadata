
Files
*****

* This endpoint does not require any authentication

Redirect to final attachment url
--------------------------------

`filename` - a query parameter for the filename of the attachment, usually of the form `/username/attachments/filename.ext`.

::

	GET /api/v1/files/[id]?filename=[filename]


Example
^^^^^^^
::

       curl -X GET https://api.ona.io/api/v1/files/1?filename=user/attachment/filename.JPG -v

Response
^^^^^^^^
.. raw:: html

    <pre>< HTTP/1.0 302 FOUND
    < Date: Mon, 23 Mar 2015 21:23:34 GMT
    < Server: WSGIServer/0.1 Python/2.7.9
    < Vary: Accept, Accept-Language, Cookie
    < Content-Language: en
    < Content-Type: text/html; charset=utf-8
    < Location: https://domain.s3.amazonaws.com/ukanga/attachments/1427114588547.jpg?...
    </pre>


Redirect to thumbnail/resized image of attachment
-------------------------------------------------

`suffix` - the query parameter defines the thumbnail size - small(240x150), medium(640x400) and large(1280X800) - for image attachments

::

	GET /api/v1/files/[id]?filename=[filename]&suffix=[small|medium|large]


Example
^^^^^^^

::

       curl -X GET https://api.ona.io/api/v1/files/1?filename=user/attachment/filename.JPG&suffix=small -v

Response
^^^^^^^^
.. raw:: html

    <pre>< HTTP/1.0 302 FOUND
    < Date: Mon, 23 Mar 2015 21:23:34 GMT
    < Server: WSGIServer/0.1 Python/2.7.9
    < Vary: Accept, Accept-Language, Cookie
    < Content-Language: en
    < Content-Type: text/html; charset=utf-8
    < Location: https://domain.s3.amazonaws.com/ukanga/attachments/1427114588547-small.jpg?...
    </pre>
