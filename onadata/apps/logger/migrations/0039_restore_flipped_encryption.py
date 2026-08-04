"""Restore encryption status for forms wrongly flipped to unencrypted."""

from django.db import migrations


def restore_flipped_encryption(apps, schema_editor):
    """Restore forms whose post-publish public key was dropped from json.

    Encryption enabled after publishing — via managed (KMS) keys or the
    API ``public_key`` field — exists only in a form's stored json and
    xml; the XLSForm file has no record of it. For forms whose stored
    json predates the pyxform 4.1.0 upgrade (skipped by migration 0031),
    ``XForm._get_survey()`` rebuilt the json from the XLSForm without
    the key and a later full save recomputed ``encrypted`` as False.

    The flip never touched the form xml, so wrongly flipped forms still
    carry the key in their xml — unlike forms legitimately unencrypted
    by an XLSForm replacement, whose replaced xml has no key.
    """
    # Use live model for get_survey_and_json_from_xlsform. This is
    # needed because apps.get_model("logger", "XForm") returns a frozen
    # version of XForm that has only the fields known at this migration
    from onadata.apps.logger.models.xform import XForm as LiveXForm

    # pylint: disable=invalid-name
    XForm = apps.get_model("logger", "XForm")
    candidates = (
        XForm.objects.filter(deleted_at__isnull=True, encrypted=False)
        .exclude(public_key="")
        .exclude(public_key__isnull=True)
        .only("id", "xml")
    )

    eta = candidates.count()

    for xform in candidates.iterator(chunk_size=100):
        eta -= 1
        print("eta", eta)

        if "base64RsaPublicKey" not in (xform.xml or ""):
            continue

        try:
            live_xform = LiveXForm.objects.get(id=xform.id)
            _, workbook_json = live_xform.get_survey_and_json_from_xlsform()
            workbook_json["public_key"] = live_xform.public_key
            XForm.objects.filter(id=xform.id).update(json=workbook_json, encrypted=True)
            print(f"Restored encryption for XForm {xform.id}")

        # pylint: disable=broad-exception-caught
        except Exception as e:
            # Best-effort repair; leave the form for manual follow-up
            print(f"Restoring encryption for XForm {xform.id} failed: {e}")


class Migration(migrations.Migration):
    dependencies = [
        ("logger", "0038_instance_last_edited_by"),
    ]

    operations = [
        migrations.RunPython(
            restore_flipped_encryption,
            reverse_code=migrations.RunPython.noop,  # migration is irreversible
        ),
    ]
