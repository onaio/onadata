from django.shortcuts import get_object_or_404

from rest_framework import filters
from rest_framework import permissions
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from onadata.libs.serializers.project_serializer import ProjectSerializer
from onadata.libs.serializers.share_project_serializer import ShareProjectSerializer
from onadata.libs.serializers.xform_serializer import XFormSerializer
from onadata.apps.api.models import Project, ProjectXForm
from onadata.apps.api import tools as utils
from onadata.apps.logger.models import XForm


class ProjectViewSet(ModelViewSet):
    """
List, Retrieve, Update, Create Project and Project Forms

Where:

- `pk` - is the project id
- `formid` - is the form id

## Register a new Project
<pre class="prettyprint">
<b>POST</b> /api/v1/projects</pre>
> Example
>
>       {
>           "url": "https://ona.io/api/v1/projects/1",
>           "owner": "https://ona.io/api/v1/users/ona",
>           "name": "project 1",
>           "date_created": "2013-07-24T13:37:39Z",
>           "date_modified": "2013-07-24T13:37:39Z"
>       }

## List of Projects

<pre class="prettyprint"><b>GET</b> /api/v1/projects</pre>
> Example
>
>       curl -X GET https://ona.io/api/v1/projects

> Response
>
>       [
>           {
>               "url": "https://ona.io/api/v1/projects/1",
>               "owner": "https://ona.io/api/v1/users/ona",
>               "name": "project 1",
>               "date_created": "2013-07-24T13:37:39Z",
>               "date_modified": "2013-07-24T13:37:39Z"
>           },
>           {
>               "url": "https://ona.io/api/v1/projects/4",
>               "owner": "https://ona.io/api/v1/users/ona",
>               "name": "project 2",
>               "date_created": "2013-07-24T13:59:10Z",
>               "date_modified": "2013-07-24T13:59:10Z"
>           }, ...
>       ]

## Retrieve Project Information

<pre class="prettyprint">
<b>GET</b> /api/v1/projects/<code>{pk}</code></pre>
> Example
>
>       curl -X GET https://ona.io/api/v1/projects/1

> Response
>
>       {
>           "url": "https://ona.io/api/v1/projects/1",
>           "owner": "https://ona.io/api/v1/users/ona",
>           "name": "project 1",
>           "date_created": "2013-07-24T13:37:39Z",
>           "date_modified": "2013-07-24T13:37:39Z"
>       }

### Assign a form to a project
To [re]assign an existing form to a project you need to `POST` a payload of
`formid=FORMID` to the endpoint below.

<pre class="prettyprint">
<b>POST</b> /api/v1/projects/<code>{pk}</code>/forms</pre>
> Example
>
>       curl -X POST -d '{"formid": 28058}' \
https://ona.io/api/v1/projects/1/forms

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
>           "owner": "ona",
>           "public": false,
>           "public_data": false,
>           "date_created": "2013-07-25T14:14:22.892Z",
>           "date_modified": "2013-07-25T14:14:22.892Z"
>       }

## Upload XLSForm to a project

<pre class="prettyprint">
<b>POST</b> /api/v1/projects/<code>{pk}</code>/forms</pre>
> Example
>
>       curl -X POST -F xls_file=@/path/to/form.xls\
 https://ona.io/api/v1/projects/1/forms

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
>           "owner": "ona",
>           "public": false,
>           "public_data": false,
>           "date_created": "2013-07-25T14:14:22.892Z",
>           "date_modified": "2013-07-25T14:14:22.892Z"
>       }

## Get Form Information for a project

<pre class="prettyprint">
<b>GET</b> /api/v1/projects/<code>{pk}</code>/forms/<code>{formid}</code>
</pre>
> Example
>
>       curl -X GET https://ona.io/api/v1/projects/1/forms/28058

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
>           "owner": "ona",
>           "public": false,
>           "public_data": false,
>           "date_created": "2013-07-25T14:14:22.892Z",
>           "date_modified": "2013-07-25T14:14:22.892Z"
>       }
    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    lookup_field = 'pk'
    extra_lookup_fields = None
    permission_classes = [permissions.DjangoObjectPermissions]
    filter_backends = (filters.DjangoObjectPermissionsFilter,)

    @action(methods=['POST', 'GET'], extra_lookup_fields=['formid', ])
    def forms(self, request, **kwargs):
        """
        POST - publish xlsform file to a specific project.

        xls_file -- xlsform file object
        """
        project = get_object_or_404(
            Project, pk=kwargs.get('pk'))
        if request.method.upper() == 'POST':
            survey = utils.publish_project_xform(request, project)

            if isinstance(survey, XForm):
                xform = XForm.objects.get(pk=survey.pk)
                serializer = XFormSerializer(
                    xform, context={'request': request})

                return Response(serializer.data, status=201)

            return Response(survey, status=400)

        qfilter = {'project': project}
        many = True
        if 'formid' in kwargs:
            many = False
            qfilter['xform__pk'] = int(kwargs.get('formid'))
        if many:
            qs = ProjectXForm.objects.filter(**qfilter)
            data = [px.xform for px in qs]
        else:
            qs = get_object_or_404(ProjectXForm, **qfilter)
            data = qs.xform

        serializer = XFormSerializer(
            data, many=many, context={'request': request})

        return Response(serializer.data)

    @action(methods=['POST'])
    def share(self, request, *args, **kwargs):
        self.object = self.get_object()

        data = {}
        for key, val in request.DATA.iteritems():
            data[key] = val
        data.update({'project': self.object.pk})

        serializer = ShareProjectSerializer(data=data)

        if serializer.is_valid():
            serializer.save()
        else:
            return Response(data=serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_204_NO_CONTENT)

