"""Decrypt submissions that failed decryption for a temporary reason."""

from django.db import migrations

# Live models are used for decrypt_instance. This is needed because
# apps.get_model("logger", "Instance") returns a frozen version of
# Instance that has only the fields known at this migration
from onadata.apps.logger.models import Instance as LiveInstance
from onadata.libs.kms.tools import decrypt_instance


# pylint: disable=unused-argument
def retry_failed_decryptions(apps, schema_editor):
    """Decrypt submissions that failed decryption for a temporary reason.

    Decryption only picks up pending submissions, so these are set to pending
    first, otherwise they would never be decrypted.
    """
    # pylint: disable=invalid-name
    Instance = apps.get_model("logger", "Instance")
    candidates = Instance.objects.filter(
        deleted_at__isnull=True,
        is_encrypted=True,
        decryption_status="failed",
    ).only("json")
    processed_count = 0
    decrypted_count = 0
    failed_count = 0
    skipped_count = 0

    for instance in candidates.iterator(chunk_size=100):
        processed_count += 1
        print(f"Processed {processed_count} submissions")

        if (instance.json or {}).get("_decryption_error") not in (
            "NOT_ALL_MEDIA_RECEIVED",
            "MAX_RETRIES_EXCEEDED",
        ):
            skipped_count += 1
            continue

        Instance.objects.filter(pk=instance.pk).update(decryption_status="pending")

        try:
            decrypt_instance(LiveInstance.objects.get(pk=instance.pk))
            decrypted_count += 1
            print(f"Decrypted Instance {instance.id}")

        # pylint: disable=broad-exception-caught
        except Exception as e:
            # Best-effort; decryption records why the submission failed
            failed_count += 1
            print(f"Decrypting Instance {instance.id} failed: {e}")

    print(
        f"Decrypted {decrypted_count} submissions,"
        f" {failed_count} failed, {skipped_count} skipped"
    )


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
