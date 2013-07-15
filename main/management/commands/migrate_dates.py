import pytz
import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import ugettext_lazy, ugettext as _
from dateutil.parser import parse

from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.contrib.admin.models import LogEntry
from odk_logger.models import XForm, Instance, InstanceHistory, Attachment
from odk_viewer.models import ParsedInstance, Export
from utils.model_tools import queryset_iterator

logging.basicConfig(level=logging.INFO)
handler = logging.FileHandler('migrate_dates.log')
handler.setLevel(logging.INFO)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger = logging.getLogger(__name__)
logger.addHandler(handler)


class Command(BaseCommand):
    args = 'upto'
    help = ugettext_lazy("Migrates all datetimes form default tz to utc")

    def handle(self, *args, **options):
        try:
            upto = args[0]
        except IndexError:
            raise CommandError(_("You must provide the datetime upto when you"
                                 " need dates to be converted to"))
        tz = pytz.timezone(settings.TIME_ZONE)
        upto = parse(upto)
        upto = upto.replace(tzinfo=pytz.timezone(settings.TIME_ZONE))
        print upto
        # User
        users = User.objects.filter(date_joined__lte=upto)
        c = 0
        t = users.count()
        logger.info("Starting on User model")
        for user in queryset_iterator(users):
            dt = user.date_joined .replace(tzinfo=tz)
            user.date_joined = dt.astimezone(pytz.utc)
            if user.last_login <= upto:
                ldt = user.last_login.replace(tzinfo=tz)
                user.last_login = ldt.astimezone(pytz.utc)
            user.save()
            c += 1
            if c % 100 == 0:
                logger.info("Users: %d of %d" % (c, t))
        logger.info("Done: Users: %d of %d" % (c, t))
        sessions = Session.objects.filter(expire_date__lte=upto)
        c = 0
        t = sessions.count()
        for session in sessions:
            dt = session.expire_date.replace(tzinfo=tz)
            session.expire_date = dt.astimezone(pytz.utc)
            session.save()
            c += 1
            if c % 100 == 0:
                logger.info("Sessions: %d of %d" % (c, t))
        logger.debug("Done: Sessions: %d of %d" % (c, t))
        logs = LogEntry.objects.filter(action_time__lte=upto)
        c = 0
        t = logs.count()
        for log in queryset_iterator(logs):
            dt = log.action_time.replace(tzinfo=tz)
            log.action_time = dt.astimezone(pytz.utc)
            log.save()
            c += 1
            if c % 100 == 0:
                logger.info("LogEntry: %d of %d" % (c, t))
        logger.debug("Done: LogEntry: %d of %d" % (c, t))
        xforms = XForm.objects.filter(date_created__lte=upto)
        c = 0
        t = xforms.count()
        for xform in queryset_iterator(xforms):
            dt = xform.date_created.replace(tzinfo=tz)
            xform.date_created = dt.astimezone(pytz.utc)
            if xform.date_modified <= upto:
                dt = xform.date_modified.replace(tzinfo=tz)
                xform.date_modified = dt.astimezone(pytz.utc)
            xform.save()
            c += 1
            if c % 100 == 0:
                logger.info("XForms: %d of %d" % (c, t))
        logger.debug("Done: XForms: %d of %d" % (c, t))
        instances = Instance.objects.filter(date_created__lte=upto)
        c = 0
        t = instances.count()
        for instance in queryset_iterator(instances):
            dt = instance.date_created.replace(tzinfo=tz)
            instance.date_created = dt.astimezone(pytz.utc)
            if instance.deleted_at and instance.deleted_at <= upto:
                dt = instance.deleted_at.replace(tzinfo=tz)
                instance.deleted_at = dt.astimezone(pytz.utc)
            try:
                instance.save()
            except Instance.DoesNotExist, e:
                logger.error(e)
            c += 1
            if c % 100 == 0:
                logger.info("Instances: %d of %d" % (c, t))
        logger.debug("Done: Instances: %d of %d" % (c, t))
        qs = ParsedInstance.objects.filter(date_created__lte=upto)
        c = 0
        t = qs.count()
        for i in queryset_iterator(qs):
            try:
                i.save()
            except Exception, e:
                logger.error(e)
            c += 1
            if c % 100 == 0:
                logger.info("ParsedInstances: %d of %d" % (c, t))
        logger.debug("Done: ParsedInstances: %d of %d" % (c, t))
        instances = InstanceHistory.objects.filter(date_created__lte=upto)
        c = 0
        t = instances.count()
        for instance in queryset_iterator(instances):
            dt = instance.date_created.replace(tzinfo=tz)
            instance.date_created = dt.astimezone(pytz.utc)
            try:
                instance.save()
            except InstanceHistory.DoesNotExist, e:
                logger.error(e)
            c += 1
            if c % 100 == 0:
                logger.info("InstanceHistory: %d of %d" % (c, t))
        logger.debug("Done: InstanceHistory: %d of %d" % (c, t))
        qs = Export.objects.filter(created_on__lte=upto)
        c = 0
        t = qs.count()
        for obj in queryset_iterator(qs):
            dt = obj.created_on.replace(tzinfo=tz)
            obj.created_on = dt.astimezone(pytz.utc)
            try:
                obj.save()
            except Export.DoesNotExist, e:
                logger.error(e)
            c += 1
            if c % 100 == 0:
                logger.info("Export: %d of %d" % (c, t))
        logger.debug("Done: Export: %d of %d" % (c, t))
