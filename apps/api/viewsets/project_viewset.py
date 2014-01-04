from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _
from rest_framework.decorators import action
from rest_framework import exceptions
from rest_framework.mixins import CreateModelMixin, ListModelMixin,\
    RetrieveModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.api import serializers
from apps.api.mixins import MultiLookupMixin
from apps.api.models import Project, ProjectXForm
from apps.api import tools as utils
from apps.odk_logger.models import XForm


class ProjectViewSet(MultiLookupMixin,
                     CreateModelMixin,
                     RetrieveModelMixin,
                     ListModelMixin,
                     GenericViewSet):
    """
List, Retrieve, Update, Create Project and Project Forms

Where:

- `owner` - is the organization to which the project(s) belong to.
- `pk` - is the project id
- `formid` - is the form id

## Register a new Organization Project
<pre class="prettyprint">
<b>POST</b> /api/v1/projects/<code>{owner}</code></pre>
> Example
>
>       {
>           "url": "https://ona.io/api/v1/projects/modilabs/1",
>           "owner": "https://ona.io/api/v1/users/modilabs",
>           "name": "project 1",
>           "date_created": "2013-07-24T13:37:39Z",
>           "date_modified": "2013-07-24T13:37:39Z"
>       }

## List of Organization's Projects

<pre class="prettyprint"><b>GET</b> /api/v1/projects <b>or</b>
<b>GET</b> /api/v1/projects/<code>{owner}</code></pre>
> Example
>
>       curl -X GET https://ona.io/api/v1/projects
>       curl -X GET https://ona.io/api/v1/projects/modilabs

> Response
>
>       [
>           {
>               "url": "https://ona.io/api/v1/projects/modilabs/1",
>               "owner": "https://ona.io/api/v1/users/modilabs",
>               "name": "project 1",
>               "date_created": "2013-07-24T13:37:39Z",
>               "date_modified": "2013-07-24T13:37:39Z"
>           },
>           {
>               "url": "https://ona.io/api/v1/projects/modilabs/4",
>               "owner": "https://ona.io/api/v1/users/modilabs",
>               "name": "project 2",
>               "date_created": "2013-07-24T13:59:10Z",
>               "date_modified": "2013-07-24T13:59:10Z"
>           }, ...
>       ]

## Retrieve Project Information

<pre class="prettyprint">
<b>GET</b> /api/v1/projects/<code>{owner}</code>/<code>{pk}</code></pre>
> Example
>
>       curl -X GET https://ona.io/api/v1/projects/modilabs/1

> Response
>
>       {
>           "url": "https://ona.io/api/v1/projects/modilabs/1",
>           "owner": "https://ona.io/api/v1/users/modilabs",
>           "name": "project 1",
>           "date_created": "2013-07-24T13:37:39Z",
>           "date_modified": "2013-07-24T13:37:39Z"
>       }

## Upload XLSForm to a project

<pre class="prettyprint">
<b>GET</b> /api/v1/projects/<code>{owner}</code>/<code>{pk}</code>/forms</pre>
> Example
>
>       curl -X POST -F xls_file=@/path/to/form.xls
>       https://ona.io/api/v1/projects/modilabs/1/forms

> Response
>
>       {
>           "url": "https://ona.io/api/v1/forms/28058",
>           "formid": 28058,
>           "uuid": "853196d7d0a74bca9ecfadbf7e2f5c1f",
>           "id_string": "Birds",
>           "sms_id_string": "Birds",
>           "title": "Birds",
>           "allows_sms": false,
>           "bamboo_dataset": "",
>           "description": "",
>           "downloadable": true,
>           "encrypted": false,
>           "is_crowd_form": false,
>           "owner": "modilabs",
>           "public": false,
>           "public_data": false,
>           "date_created": "2013-07-25T14:14:22.892Z",
>           "date_modified": "2013-07-25T14:14:22.892Z"
>       }

## Get Form Information for a project

<pre class="prettyprint">
<b>GET</b> /api/v1/projects/<code>{owner}</code>/<code>{pk}</code>/forms/<code>
{formid}</code></pre>
> Example
>
>       curl -X GET https://ona.io/api/v1/projects/modilabs/1/forms/28058

> Response
>
>       {
>           "url": "https://ona.io/api/v1/forms/28058",
>           "formid": 28058,
>           "uuid": "853196d7d0a74bca9ecfadbf7e2f5c1f",
>           "id_string": "Birds",
>           "sms_id_string": "Birds",
>           "title": "Birds",
>           "allows_sms": false,
>           "bamboo_dataset": "",
>           "description": "",
>           "downloadable": true,
>           "encrypted": false,
>           "is_crowd_form": false,
>           "owner": "modilabs",
>           "public": false,
>           "public_data": false,
>           "date_created": "2013-07-25T14:14:22.892Z",
>           "date_modified": "2013-07-25T14:14:22.892Z"
>       }
    """
    queryset = Project.objects.all()
    serializer_class = serializers.ProjectSerializer
    lookup_fields = ('owner', 'pk')
    lookup_field = 'owner'
    extra_lookup_fields = None

    def get_queryset(self):
        user = self.request.user
        if user.is_anonymous():
            user = User.objects.get(pk=-1)
        return user.project_creator.all()

    def get_object(self, queryset=None):
        pk = self.kwargs.get('pk', None)
        if pk is not None:
            try:
                int(pk)
            except ValueError:
                raise exceptions.ParseError(
                    detail=_(u"The path parameter {pk} "
                             u"should be a number, '%s' given instead." % pk))
        print queryset
        return super(ProjectViewSet, self).get_object(queryset)

    def list(self, request, **kwargs):
        filter = {}
        if 'owner' in kwargs:
            filter['organization__username'] = kwargs['owner']
        # filter['created_by'] = request.user
        qs = self.get_queryset()
        qs = self.filter_queryset(qs)
        self.object_list = qs.filter(**filter)
        serializer = self.get_serializer(self.object_list, many=True)
        return Response(serializer.data)

    @action(methods=['POST', 'GET'], extra_lookup_fields=['formid', ])
    def forms(self, request, **kwargs):
        """
        POST - publish xlsform file to a specific project.

        xls_file -- xlsform file object
        """
        project = get_object_or_404(
            Project, pk=kwargs.get('pk', None),
            organization__username=kwargs.get('owner', None))
        if request.method.upper() == 'POST':
            survey = utils.publish_project_xform(request, project)
            if isinstance(survey, XForm):
                xform = XForm.objects.get(pk=survey.pk)
                serializer = serializers.XFormSerializer(
                    xform, context={'request': request})
                return Response(serializer.data, status=201)
            return Response(survey, status=400)
        filter = {'project': project}
        many = True
        if 'formid' in kwargs:
            many = False
            filter['xform__pk'] = int(kwargs.get('formid'))
        if many:
            qs = ProjectXForm.objects.filter(**filter)
            data = [px.xform for px in qs]
        else:
            qs = get_object_or_404(ProjectXForm, **filter)
            data = qs.xform
        serializer = serializers.XFormSerializer(
            data, many=many, context={'request': request})
        return Response(serializer.data)
