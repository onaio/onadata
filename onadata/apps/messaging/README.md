Messaging
=========

Adds support to create and view messages via an API.

API Endpoints
-------------

GET /api/messaging - returns an empty list, will return a list of messages given `xform` or `project` or `user` query parameters.

GET /api/messaging/[pk] - returns a specific message with matching pk.

DELETE /api/messaging/[pk] - deletes a specific message with matching pk.

POST /api/messaging - create a new message, requires an xform or a project and the message.
