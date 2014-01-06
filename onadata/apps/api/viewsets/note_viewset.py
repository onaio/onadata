from rest_framework import permissions
from rest_framework.viewsets import ModelViewSet

from onadata.apps.api import serializers
from onadata.apps.odk_logger.models import Note


class NoteViewSet(ModelViewSet):
    """## Add Notes to a submission

A `POST` payload of parameters:

    `note` - the note string to add to a data point
    `instance` - the data point id

 <pre class="prettyprint">
  <b>POST</b> /api/v1/notes</pre>

Payload

    {"instance": 1, "note": "This is a note."}

  > Response
  >
  >     {
  >          "id": 1,
  >          "instance": 1,
  >          "note": "This is a note."
  >          ...
  >     }
  >
  >     HTTP 201 OK

# Get List of notes for a data point

A `GET` request will return the list of notes applied to a data point.

 <pre class="prettyprint">
  <b>GET</b> /api/v1/notes</pre>


  > Response
  >
  >     [{
  >          "id": 1,
  >          "instance": 1,
  >          "note": "This is a note."
  >          ...
  >     }, ...]
  >
  >
  >        HTTP 200 OK
"""
    queryset = Note.objects.all()
    serializer_class = serializers.NoteSerializer
    permission_classes = [permissions.DjangoModelPermissions,
                          permissions.IsAuthenticated, ]

    def get_queryset(self):
        return Note.objects.filter(instance__xform__user=self.request.user)
