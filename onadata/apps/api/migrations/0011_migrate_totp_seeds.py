# -*- coding: utf-8 -*-
"""Move existing authenticator seeds into the encrypted device.

django-otp's ``TOTPDevice`` holds the seed as plaintext, so it can be read here
and re-stored encrypted; each row is copied to an ``EncryptedTOTPDevice`` and
the plaintext original removed. ``last_t`` is carried over so a just-used code
cannot be replayed across the move. Existing recovery codes are not migrated:
the set they replaced held only keyed hashes, which cannot be decrypted, so
owners regenerate theirs once -- the authenticator itself keeps working.

Requires ``TWO_FACTOR_FIELD_ENCRYPTION_KEYS`` to be set wherever rows exist.
"""

from django.db import migrations

from onadata.libs.utils.field_encryption import encrypt

TOTP_DEVICE_NAME = "default"

_CARRY_FIELDS = (
    "confirmed",
    "last_t",
    "drift",
    "throttling_failure_timestamp",
    "throttling_failure_count",
    "created_at",
    "last_used_at",
)


def encrypt_existing_seeds(apps, schema_editor):
    old_model = apps.get_model("otp_totp", "TOTPDevice")
    new_model = apps.get_model("api", "EncryptedTOTPDevice")
    for old in old_model.objects.filter(name=TOTP_DEVICE_NAME):
        carried = {field: getattr(old, field) for field in _CARRY_FIELDS}
        new_model.objects.create(
            user_id=old.user_id,
            name=old.name,
            encrypted_key=encrypt(old.key),
            **carried,
        )
        old.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0010_encrypt_second_factor_secrets"),
        ("otp_totp", "0003_add_timestamps"),
    ]

    operations = [
        migrations.RunPython(encrypt_existing_seeds, migrations.RunPython.noop),
    ]
