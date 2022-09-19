# -*- coding: utf-8 -*-
"""onadata.libs.models.signals module"""
import django.dispatch

from onadata.apps.logger.models import XForm

# pylint: disable=invalid-name
xform_tags_add = django.dispatch.Signal()
xform_tags_delete = django.dispatch.Signal()


# pylint: disable=unused-argument
@django.dispatch.receiver(xform_tags_add, sender=XForm)
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
@django.dispatch.receiver(xform_tags_delete, sender=XForm)
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
