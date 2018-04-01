# -*- coding: utf-8 -*-
"""
RestService model
"""
import importlib
from future.utils import python_2_unicode_compatible

from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.utils.translation import ugettext_lazy

from onadata.apps.logger.models.xform import XForm
from onadata.apps.main.models import MetaData
from onadata.apps.restservice import SERVICE_CHOICES
from onadata.libs.utils.common_tags import GOOGLE_SHEET, TEXTIT


@python_2_unicode_compatible
class RestService(models.Model):
    """
    Properties for an external service.
    """

    class Meta:
        app_label = 'restservice'
        unique_together = ('service_url', 'xform', 'name')

    service_url = models.URLField(ugettext_lazy("Service URL"))
    xform = models.ForeignKey(XForm)
    name = models.CharField(max_length=50, choices=SERVICE_CHOICES)
    date_created = models.DateTimeField(
        auto_now_add=True, null=True, blank=True)
    date_modified = models.DateTimeField(auto_now=True, null=True, blank=True)
    active = models.BooleanField(ugettext_lazy("Active"), default=True,
                                 blank=False, null=False)
    inactive_reason = models.TextField(ugettext_lazy("Inactive reason"),
                                       blank=True, default="")

    def __str__(self):
        return u"%s:%s - %s" % (self.xform, self.long_name, self.service_url)

    def get_service_definition(self):
        """
        Returns ServiceDefinition class
        """
        services_to_modules = getattr(settings, 'REST_SERVICES_TO_MODULES', {})
        module_name = services_to_modules.get(
            self.name, 'onadata.apps.restservice.services.%s' % self.name)
        module = importlib.import_module(module_name)

        return module.ServiceDefinition

    @property
    def long_name(self):
        """
        Service verbose name.
        """
        service_definition = self.get_service_definition()

        return service_definition.verbose_name


def delete_metadata(sender, instance, **kwargs):  # pylint: disable=W0613
    """
    Delete related metadata on deletion of the RestService.
    """
    if instance.name in [TEXTIT, GOOGLE_SHEET]:
        MetaData.objects.filter(  # pylint: disable=no-member
            object_id=instance.xform.id,
            data_type=instance.name).delete()


post_delete.connect(
    delete_metadata, sender=RestService, dispatch_uid='delete_metadata')


# pylint: disable=W0613
def propagate_merged_datasets(sender, instance, **kwargs):
    """
    Propagate the service to the individual forms of a merged dataset.
    """
    created = kwargs.get('created')
    if created and instance.xform.is_merged_dataset:
        for xform in instance.xform.mergedxform.xforms.all():
            RestService.objects.create(
                service_url=instance.service_url,
                xform=xform,
                name=instance.name)


post_save.connect(
    propagate_merged_datasets,
    sender=RestService,
    dispatch_uid='propagate_merged_datasets')


# pylint: disable=W0613
def delete_merged_datasets_service(sender, instance, **kwargs):
    """
    Delete the service to the individual forms of a merged dataset.
    """
    if instance.xform.is_merged_dataset:
        for xform in instance.xform.mergedxform.xforms.all():
            try:
                service = RestService.objects.get(
                    service_url=instance.service_url,
                    xform=xform,
                    name=instance.name)
            except RestService.DoesNotExist:
                pass
            else:
                service.delete()


post_delete.connect(
    delete_merged_datasets_service,
    sender=RestService,
    dispatch_uid='propagate_merged_datasets')
