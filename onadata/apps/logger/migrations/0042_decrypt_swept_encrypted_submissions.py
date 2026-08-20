"""Decrypt submissions whose ciphertext was swept by the attachment sweep."""

from django.db import migrations

# Live models are used for decrypt_instance. This is needed because
# apps.get_model("logger", "Instance") returns a frozen version of
# Instance that has only the fields known at this migration
from onadata.apps.logger.models import Instance as LiveInstance
from onadata.libs.kms.tools import decrypt_instance


# pylint: disable=unused-argument
def decrypt_swept_encrypted_submissions(apps, schema_editor):
    """Restore and decrypt submissions whose ciphertext was wrongly swept.

    While a managed form's ``encrypted`` flag was False — flipped by the
    stale-json bug repaired in logger.0039, or turned off while devices
    still held an encrypted form version — ``get_expected_media`` did not
    recognise incoming encrypted envelopes, so the attachment sweep in
    ``save_attachments`` soft-deleted their ciphertext right after
    creation and decryption failed with no files.
    """
    # pylint: disable=invalid-name
    Instance = apps.get_model("logger", "Instance")
    candidates = Instance.objects.filter(
        deleted_at__isnull=True,
        is_encrypted=True,
        decryption_status="failed",
    )
    decrypted_count = 0
    failed_count = 0
    skipped_count = 0

    for instance in candidates.iterator(chunk_size=100):
        if (instance.json or {}).get("_decryption_error") != "INVALID_SUBMISSION":
            skipped_count += 1
            continue

        instance.attachments.filter(deleted_at__isnull=False).update(deleted_at=None)

        try:
            decrypt_instance(LiveInstance.objects.get(pk=instance.pk))
            decrypted_count += 1
            print(f"Decrypted Instance {instance.id}")

        # pylint: disable=broad-exception-caught
        except Exception as e:
            # Best-effort repair; leave the submission for manual follow-up
            failed_count += 1
            print(f"Decrypting Instance {instance.id} failed: {e}")

    print(
        f"Decrypted {decrypted_count} submissions,"
        f" {failed_count} failed, {skipped_count} skipped"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("logger", "0041_project_date_created_indexes"),
    ]

    operations = [
        migrations.RunPython(
            decrypt_swept_encrypted_submissions,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
