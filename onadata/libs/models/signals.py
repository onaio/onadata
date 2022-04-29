# -*- coding: utf-8 -*-
"""onadata.libs.models.signals module"""
import django.dispatch

from onadata.apps.logger.models import XForm

XFORM_TAGS_ADD = django.dispatch.Signal(providing_args=["xform", "tags"])
XFORM_TAGS_DELETE = django.dispatch.Signal(providing_args=["xform", "tag"])


# pylint: disable=unused-argument
@django.dispatch.receiver(XFORM_TAGS_ADD, sender=XForm)
def add_tags_to_xform_instances(sender, **kwargs):
    """Adds tags to an xform instance."""
    xform = kwargs.get("xform", None)
    tags = kwargs.get("tags", None)
    if isinstance(xform, XForm) and isinstance(tags, list):
        # update existing instances with the new tag
        for instance in xform.instances.all():
            for tag in tags:
                if tag not in instance.tags.names():
                    instance.tags.add(tag)
            # ensure mongodb is updated
            instance.parsed_instance.save()


# pylint: disable=unused-argument
@django.dispatch.receiver(XFORM_TAGS_DELETE, sender=XForm)
def delete_tag_from_xform_instances(sender, **kwargs):
    """Deletes tags associated with an xform when it is deleted."""
    xform = kwargs.get("xform", None)
    tag = kwargs.get("tag", None)
    if isinstance(xform, XForm) and isinstance(tag, str):
        # update existing instances with the new tag
        for instance in xform.instances.all():
            if tag in instance.tags.names():
                instance.tags.remove(tag)
                # ensure mongodb is updated
                instance.parsed_instance.save()
