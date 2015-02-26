from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.translation import ugettext_lazy

from onadata.apps.main.models.audit import Audit


class Command(BaseCommand):
    help = ugettext_lazy("migrate audit log from mongo to postgres")

    def handle(self, *args, **kwargs):
        auditlog = settings.MONGO_DB.auditlog
        for item in auditlog.find():
            del item['_id']
            Audit(json=item).save()
