"""Make submissions that failed decryption for a temporary reason pending again."""

from django.db import migrations


# pylint: disable=unused-argument
def retry_failed_decryptions(apps, schema_editor):
    """Set submissions that failed decryption for a temporary reason to pending.

    Decryption only picks up pending submissions, so these would otherwise
    never be decrypted.
    """
    # pylint: disable=invalid-name
    Instance = apps.get_model("logger", "Instance")
    candidates = Instance.objects.filter(
        deleted_at__isnull=True,
        is_encrypted=True,
        decryption_status="failed",
    ).only("json")
    retried_count = 0
    skipped_count = 0

    for instance in candidates.iterator(chunk_size=100):
        if (instance.json or {}).get("_decryption_error") not in (
            "NOT_ALL_MEDIA_RECEIVED",
            "MAX_RETRIES_EXCEEDED",
        ):
            skipped_count += 1
            continue

        Instance.objects.filter(pk=instance.pk).update(decryption_status="pending")
        retried_count += 1

    print(f"Retrying {retried_count} submissions, {skipped_count} skipped")


class Migration(migrations.Migration):
    dependencies = [
        ("logger", "0048_alter_instance_decryption_status"),
    ]

    operations = [
        migrations.RunPython(
            retry_failed_decryptions,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
