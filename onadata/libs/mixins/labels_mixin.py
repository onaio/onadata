from django import forms
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from taggit.forms import TagField

from onadata.apps.logger.models import XForm
from onadata.libs.models.signals import xform_tags_add, xform_tags_delete


class TagForm(forms.Form):
    tags = TagField()


def _labels_post(request, instance):
    """Process a post request to labels.

    :param request: The HTTP request to extract data from.
    :param instance: The instance to set tags on.
    :returns: A HTTP status code or None.
    """
    form = TagForm(request.DATA)

    if form.is_valid():
        tags = form.cleaned_data.get('tags', None)

        if tags:
            for tag in tags:
                instance.tags.add(tag)

            if isinstance(instance, XForm):
                xform_tags_add.send(
                    sender=XForm, xform=instance, tags=tags)

            return 201


def _labels_delete(label, xform):
    count = xform.tags.count()
    xform.tags.remove(label)
    xform_tags_delete.send(sender=XForm, xform=xform, tag=label)

    # Accepted, label does not exist hence nothing removed
    http_status = status.HTTP_202_ACCEPTED if count == xform.tags.count()\
        else status.HTTP_200_OK

    return [http_status, list(xform.tags.names())]


def process_label_request(request, label, instance):
    http_status = status.HTTP_200_OK

    if request.method == 'POST':
        http_status = _labels_post(request, instance)

    if request.method == 'GET' and label:
        data = [tag['name']
                for tag in instance.tags.filter(name=label).values('name')]
    elif request.method == 'DELETE' and label:
        http_status, data = _labels_delete(label, instance)
    else:
        data = list(instance.tags.names())

    return Response(data, status=http_status)


class LabelsMixin(object):
    @action(methods=['GET', 'POST', 'DELETE'], extra_lookup_fields=['label', ])
    def labels(self, request, format='json', **kwargs):
        xform = self.get_object()
        label = kwargs.get('label')
        return process_label_request(request, label, xform)
