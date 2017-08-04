import six
import uuid
import sys
import traceback

from django.core.mail import mail_admins
from django.utils.translation import ugettext as _
from django.conf import settings

from raven.contrib.django.raven_compat.models import client


def str_to_bool(s):
    """Return boolean True or False if string s represents a boolean value"""
    # no need to convert boolean values otherwise it will always be false
    if isinstance(s, bool):
        return s

    TRUE_VALUES = ['TRUE', 'T', '1', 1]
    s = s.upper() if isinstance(s, six.string_types) else s

    return s in TRUE_VALUES


def get_boolean_value(str_var, default=None):
    if isinstance(str_var, basestring) and \
            str_var.lower() in ['true', 'false']:
        return str_to_bool(str_var)

    return str_var if default else False


def getUUID():
    '''
    Return UUID
    '''
    return uuid.uuid4().hex


def report_exception(subject, info, exc_info=None):
    # Add hostname to subject mail

    subject = "{0} - {1}".format(subject, settings.HOSTNAME)
    if exc_info:
        cls, err = exc_info[:2]
        message = _(u"Exception in request:"
                    u" %(class)s: %(error)s")\
            % {'class': cls.__name__, 'error': err}
        message += u"".join(traceback.format_exception(*exc_info))

        # send to sentry
        try:
            client.captureException(exc_info)
        except Exception:
            # fail silently
            pass
    else:
        message = u"%s" % info

    if settings.DEBUG or settings.TESTING_MODE:
        sys.stdout.write("Subject: %s\n" % subject)
        sys.stdout.write("Message: %s\n" % message)
    else:
        mail_admins(subject=subject, message=message)
