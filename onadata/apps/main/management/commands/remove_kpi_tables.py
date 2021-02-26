from django.db import connection
from django.core.management.base import BaseCommand
from django.utils.translation import ugettext_lazy


def drop_table(table):
    cursor = connection.cursor()
    # Using DROP instead od Delete to remove entire table from DB
    # Calling cascade to delete data referenced from other tables
    sql = f"DROP TABLE {table} CASCADE;"
    cursor.execute(sql)


class Command(BaseCommand):
    help = ugettext_lazy("Drop Formbuilder tables and data from Onadata DB")

    def handle(self, *args, **kwargs):
        kpi_tables = [
            'django_migrations',
            'django_content_type',
            'auth_user',
            'auth_group',
            'auth_permission',
            'auth_group_permissions',
            'auth_user_groups',
            'auth_user_user_permissions',
            'constance_config',
            'django_celery_beat_periodictasks',
            'django_celery_beat_crontabschedule',
            'django_celery_beat_intervalschedule',
            'django_celery_beat_periodictask',
            'django_celery_beat_solarschedule',
            'django_admin_log',
            'authtoken_token',
            'django_digest_partialdigest',
            'taggit_tag',
            'taggit_taggeditem',
            'kpi_collection',
            'kpi_asset',
            'reversion_revision',
            'reversion_version',
            'kpi_assetversion',
            'kpi_importtask',
            'kpi_authorizedapplication',
            'kpi_taguid',
            'kpi_objectpermission',
            'kpi_assetsnapshot',
            'kpi_onetimeauthenticationkey',
            'kpi_usercollectionsubscription',
            'kpi_exporttask',
            'kpi_assetfile',
            'hub_sitewidemessage',
            'hub_configurationfile',
            'hub_formbuilderpreference',
            'hub_extrauserdetail',
            'hub_perusersetting',
            'oauth2_provider_application',
            'oauth2_provider_application_id_seq',
            'django_session',
            'oauth2_provider_accesstoken',
            'oauth2_provider_accesstoken_id_seq',
            'oauth2_provider_grant',
            'oauth2_provider_grant_id_seq',
            'django_digest_usernonce',
            'oauth2_provider_refreshtoken',
            'oauth2_provider_refreshtoken_id_seq',
            'registration_registrationprofile',
            'hook_hook',
            'hook_hooklog',
            'external_integrations_corsmodel',
            'help_inappmessage',
            'help_inappmessagefile',
            'help_inappmessageuserinteractions'
        ]
        for table in kpi_tables:
            # Drop table with existing data
            drop_table(table)

        self.stdout.write(
            "Done deleting KPI tables and data!!!"
        )
