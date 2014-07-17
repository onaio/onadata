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
    """Add a label to an instance.

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
                xform_tags_add.send(sender=XForm, xform=instance, tags=tags)

            return 201


def _labels_delete(label, instance):
    """Delete a label from an instance.

    :param instance: object to delete label from.
    :param label: the label to delete.

    :returns the status and all the tags.
    """
    count = instance.tags.count()
    instance.tags.remove(label)

    if isinstance(instance, XForm):
        xform_tags_delete.send(sender=XForm, xform=instance, tag=label)

    # Accepted, label does not exist hence nothing removed
    http_status = status.HTTP_202_ACCEPTED if count == instance.tags.count()\
        else status.HTTP_200_OK

    return [http_status, list(instance.tags.names())]


def process_label_request(request, label, instance):
    """Process request to labels endpoint.

    :param request: HTTP request object.
    :param label: label that is being acted on.
    :param instance: object that label is applied to.

    :returns: A response object based on the type of request.
    """
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
