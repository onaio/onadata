import json
from django import forms
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _
from rest_framework import exceptions, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.viewsets import ViewSet
from taggit.forms import TagField

from onadata.apps.api.tools import get_accessible_forms, get_xform
from onadata.apps.logger.models import Instance
from onadata.apps.viewer.models.parsed_instance import ParsedInstance
from onadata.libs.utils.user_auth import check_and_set_form_by_id,\
    check_and_set_form_by_id_string


class DataViewSet(ViewSet):
    """
This endpoint provides access to submitted data in JSON format. Where:

* `owner` - is organization or user whom the data belongs to
* `formid` - the form unique identifier
* `dataid` - submission data unique identifier

## GET JSON List of data end points
This is a json list of the data end points of `owner` forms
 and/or including public forms and forms shared with `owner`.
<pre class="prettyprint">
<b>GET</b> /api/v1/data
<b>GET</b> /api/v1/data/<code>{owner}</code></pre>

> Example
>
>       curl -X GET https://ona.io/api/v1/data/modilabs

> Response
>
>        {
>            "dhis2form": "https://ona.io/api/v1/data/modilabs/4240",
>            "exp_one": "https://ona.io/api/v1/data/modilabs/13789",
>            "userone": "https://ona.io/api/v1/data/modilabs/10417",
>        }

## Get Submitted data for a specific form
Provides a list of json submitted data for a specific form.
<pre class="prettyprint">
<b>GET</b> /api/v1/data/<code>{owner}</code>/<code>{formid}</code></pre>
> Example
>
>       curl -X GET https://ona.io/api/v1/data/modilabs/22845

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

Get a single specific submission json data providing `formid`
 and `dataid` as url path parameters, where:

* `owner` - is organization or user whom the data belongs to
* `formid` - is the identifying number for a specific form
* `dataid` - is the unique id of the data, the value of `_id` or `_uuid`

<pre class="prettyprint">
<b>GET</b> /api/v1/data/<code>{owner}</code>/<code>{formid}</code>/<code>\
{dataid}</code></pre>
> Example
>
>       curl -X GET https://ona.io/api/v1/data/modilabs/22845/4503

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
<a href="http://www.mongodb.org/display/DOCS/Querying.">
http://www.mongodb.org/display/DOCS/Querying</a>.

For more details see
<a href="https://github.com/modilabs/formhub/wiki/Formhub-Access-Points-(API)#
api-parameters">
API Parameters</a>.
<pre class="prettyprint">
<b>GET</b> /api/v1/data/<code>{owner}</code>/<code>{formid}</code>\
?query={"field":"value"}</pre>
> Example
>
>       curl -X GET  https://ona.io/api/v1/data/modilabs/22845\
?query={"kind": "monthly"}

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
<b>GET</b> /api/v1/data/<code>{owner}</code>?<code>tags</code>=<code>tag1,tag2
</code></pre>
<pre class="prettyprint">
<b>GET</b> /api/v1/data/<code>{owner}</code>/<code>{formid}</code>?<code>tags\
</code>=<code>tag1,tag2</code></pre>

> Example
>
>       curl -X GET https://ona.io/api/v1/data/modilabs/22845?tags=monthly

## Tag a submission data point

A `POST` payload of parameter `tags` with a comma separated list of tags.

Examples

- `animal fruit denim` - space delimited, no commas
- `animal, fruit denim` - comma delimited

<pre class="prettyprint">
<b>POST</b> /api/v1/data/<code>{owner}</code>/<code>{formid}</code>/<code>\
{dataid}</code>/labels</pre>

Payload

    {"tags": "tag1, tag2"}

## Delete a specific tag from a submission

<pre class="prettyprint">
<b>DELETE</b> /api/v1/data/<code>{owner}</code>/<code>{formid}</code>/<code>\
{dataid}</code>/labels/<code>tag_name</code></pre>

> Request
>
>       curl -X DELETE \
https://ona.io/api/v1/data/modilabs/28058/20/labels/tag1
or to delete the tag "hello world"
>
>       curl -X DELETE \
https://ona.io/api/v1/data/modilabs/28058/20/labels/hello%20world
>
> Response
>
>        HTTP 200 OK
"""
    permission_classes = [permissions.IsAuthenticated, ]
    lookup_field = 'owner'
    lookup_fields = ('owner', 'formid', 'dataid')
    extra_lookup_fields = None

    queryset = Instance.objects.all()

    def _get_formlist_data_points(self, request, owner=None):
        xforms = get_accessible_forms(owner)
        # filter by tags if available.
        tags = self.request.QUERY_PARAMS.get('tags', None)
        if tags and isinstance(tags, basestring):
            tags = tags.split(',')
            xforms = xforms.filter(tags__name__in=tags).distinct()
        rs = {}
        for xform in xforms.distinct():
            point = {u"%s" % xform.id_string:
                     reverse("data-list", kwargs={
                             "formid": xform.pk,
                             "owner": xform.user.username},
                             request=request)}
            rs.update(point)
        return rs

    def _get_form_data(self, xform, **kwargs):
        query = kwargs.get('query', {})
        query = query if query is not None else {}
        if xform:
            query[ParsedInstance.USERFORM_ID] =\
                u'%s_%s' % (xform.user.username, xform.id_string)
        query = json.dumps(query) if isinstance(query, dict) else query
        margs = {
            'query': query,
            'fields': kwargs.get('fields', None),
            'sort': kwargs.get('sort', None)
        }
        cursor = ParsedInstance.query_mongo_minimal(**margs)
        records = list(record for record in cursor)
        return records

    def list(self, request, owner=None, formid=None, dataid=None, **kwargs):
        data = None
        xform = None
        query = None
        tags = self.request.QUERY_PARAMS.get('tags', None)
        if owner is None and not request.user.is_anonymous():
            owner = request.user.username
        if not formid and not dataid and not tags:
            data = self._get_formlist_data_points(request, owner)

        if formid:
            xform = get_xform(formid, request)

            query = {}
            query[ParsedInstance.USERFORM_ID] = \
                u'%s_%s' % (xform.user.username, xform.id_string)

        if xform and dataid and dataid == 'labels':
            return Response(list(xform.tags.names()))
        if dataid:
            if query:
                query.update({'_id': int(dataid)})
            else:
                query = {'_id': int(dataid)}
        rquery = request.QUERY_PARAMS.get('query', None)
        if rquery:
            rquery = json.loads(rquery)
            if query:
                query.update(rquery)
            else:
                query = rquery
        if tags:
            query = query if query else {}
            query['_tags'] = {'$all': tags.split(',')}
        if xform:
            data = self._get_form_data(xform, query=query)
        if not xform and not data:
            xforms = get_accessible_forms(owner)
            if not query:
                query = {}
            query[ParsedInstance.USERFORM_ID] = {
                '$in': [
                    u'%s_%s' % (form.user.username, form.id_string)
                    for form in xforms]
            }
            # query['_id'] = {'$in': [form.pk for form in xforms]}
            data = self._get_form_data(xform, query=query)
        if dataid and len(data):
            data = data[0]
        return Response(data)

    @action(methods=['GET', 'POST', 'DELETE'], extra_lookup_fields=['label', ])
    def labels(self, request, owner, formid, dataid, **kwargs):
        class TagForm(forms.Form):
            tags = TagField()
        if owner is None and not request.user.is_anonymous():
            owner = request.user.username
        xform = None
        try:
            xform = check_and_set_form_by_id(int(formid), request)
        except ValueError:
            xform = check_and_set_form_by_id_string(formid, request)
        if not xform:
            raise exceptions.PermissionDenied(
                _("You do not have permission to view data from this form."))
        status = 400
        instance = get_object_or_404(ParsedInstance, instance__pk=int(dataid))
        if request.method == 'POST':
            form = TagForm(request.DATA)
            if form.is_valid():
                tags = form.cleaned_data.get('tags', None)
                if tags:
                    for tag in tags:
                        instance.instance.tags.add(tag)
                    instance.save()
                    status = 201
        label = kwargs.get('label', None)
        if request.method == 'GET' and label:
            data = [
                tag['name'] for tag in
                instance.instance.tags.filter(name=label).values('name')]
        elif request.method == 'DELETE' and label:
            count = instance.instance.tags.count()
            instance.instance.tags.remove(label)
            # Accepted, label does not exist hence nothing removed
            if count == instance.instance.tags.count():
                status = 202
            data = list(instance.instance.tags.names())
        else:
            data = list(instance.instance.tags.names())
        if request.method == 'GET':
            status = 200
        return Response(data, status=status)
