"""Make submissions that failed decryption for a temporary reason pending again."""

from django.db import migrations
from django.db.models import Q


# pylint: disable=unused-argument
def retry_failed_decryptions(apps, schema_editor):
    """Set submissions that failed decryption for a temporary reason to pending.

    Decryption only picks up pending submissions, so these would otherwise
    never be decrypted.
    """
    # pylint: disable=invalid-name
    Instance = apps.get_model("logger", "Instance")
    Instance.objects.filter(
        Q(json__contains={"_decryption_error": "NOT_ALL_MEDIA_RECEIVED"})
        | Q(json__contains={"_decryption_error": "MAX_RETRIES_EXCEEDED"}),
        decryption_status="failed",
    ).update(decryption_status="pending")


class Migration(migrations.Migration):
    dependencies = [
        ("logger", "0048_alter_instance_decryption_status"),
    ]

    operations = [
        migrations.RunPython(retry_failed_decryptions, migrations.RunPython.noop),
    ]
