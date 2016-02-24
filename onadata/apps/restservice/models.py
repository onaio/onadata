from django.db import models
from django.db.models.signals import post_delete
from django.utils.translation import ugettext_lazy

from onadata.apps.logger.models.xform import XForm
from onadata.apps.main.models import MetaData
from onadata.apps.restservice import SERVICE_CHOICES

from onadata.libs.utils.common_tags import TEXTIT


class RestService(models.Model):

    class Meta:
        app_label = 'restservice'
        unique_together = ('service_url', 'xform', 'name')

    service_url = models.URLField(ugettext_lazy("Service URL"))
    xform = models.ForeignKey(XForm)
    name = models.CharField(max_length=50, choices=SERVICE_CHOICES)

    def __unicode__(self):
        return u"%s:%s - %s" % (self.xform, self.long_name, self.service_url)

    def get_service_definition(self):
        m = __import__(''.join(['onadata.apps.restservice.services.',
                       self.name]),
                       globals(), locals(), ['ServiceDefinition'])
        return m.ServiceDefinition

    @property
    def long_name(self):
        sv = self.get_service_definition()
        return sv.verbose_name


def delete_metadata(sender, instance, **kwargs):
    if instance.name == TEXTIT:
        MetaData.objects.filter(
            object_id=instance.xform.id, data_type=instance.name).delete()

post_delete.connect(delete_metadata, sender=RestService,
                    dispatch_uid='delete_metadata')
