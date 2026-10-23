"""Make submissions that failed decryption for a temporary reason pending again."""

from django.db import migrations

TEMPORARY_ERRORS = ("NOT_ALL_MEDIA_RECEIVED", "MAX_RETRIES_EXCEEDED")
BATCH_SIZE = 1000


# pylint: disable=unused-argument
def retry_failed_decryptions(apps, schema_editor):
    """Set submissions that failed decryption for a temporary reason to pending.

    Decryption only picks up pending submissions, so these would otherwise
    never be decrypted.
    """
    # pylint: disable=invalid-name
    Instance = apps.get_model("logger", "Instance")
    failed = Instance.objects.filter(decryption_status="failed").values_list(
        "pk", "json"
    )
    pks = []

    for pk, json in failed.iterator(chunk_size=BATCH_SIZE):
        if (json or {}).get("_decryption_error") in TEMPORARY_ERRORS:
            pks.append(pk)

        if len(pks) == BATCH_SIZE:
            Instance.objects.filter(pk__in=pks).update(decryption_status="pending")
            pks = []

    if pks:
        Instance.objects.filter(pk__in=pks).update(decryption_status="pending")


class Migration(migrations.Migration):
    dependencies = [
        ("logger", "0048_alter_instance_decryption_status"),
    ]

    operations = [
        migrations.RunPython(retry_failed_decryptions, migrations.RunPython.noop),
    ]
