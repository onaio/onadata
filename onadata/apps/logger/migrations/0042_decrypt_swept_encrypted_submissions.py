"""Decrypt submissions whose ciphertext was swept by the attachment sweep."""

from django.db import migrations


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
    from onadata.apps.logger.models import Instance
    from onadata.libs.kms.tools import decrypt_instance

    candidates = (
        Instance.objects.filter(
            deleted_at__isnull=True,
            is_encrypted=True,
            xform__kms_keys__isnull=False,
            attachments__deleted_at__isnull=False,
        )
        .exclude(decryption_status=Instance.DecryptionStatus.SUCCESS)
        .distinct()
    )

    eta = candidates.count()

    for instance in candidates.iterator(chunk_size=100):
        eta -= 1
        print("eta", eta)

        instance.attachments.filter(deleted_at__isnull=False).update(deleted_at=None)

        try:
            decrypt_instance(instance)
            print(f"Decrypted Instance {instance.id}")

        # pylint: disable=broad-exception-caught
        except Exception as e:
            # Best-effort repair; leave the submission for manual follow-up
            print(f"Decrypting Instance {instance.id} failed: {e}")


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
