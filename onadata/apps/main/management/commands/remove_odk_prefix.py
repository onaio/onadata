from django.core.management.base import BaseCommand
from django.db import connection
from django.utils.translation import ugettext_lazy


class Command(BaseCommand):
    help = ugettext_lazy("Remove from logger and viewer apps")

    option_list = BaseCommand.option_list

    def handle(self, *args, **kwargs):
        cursor = connection.cursor()
        cursor.execute('UPDATE south_migrationhistory SET app_name=%s WHERE '
                       'app_name=%s', ['logger', 'odk_logger'])
        cursor.execute('UPDATE south_migrationhistory SET app_name=%s WHERE '
                       'app_name=%s', ['viewer', 'odk_viewer'])
