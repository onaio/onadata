# -*- coding: utf-8 -*-
"""Re-encrypt second-factor secrets under the current primary key.

Roll a new key in at the front of ``TWO_FACTOR_FIELD_ENCRYPTION_KEYS``, run
this command, then drop the old key: every authenticator seed and recovery code
is decrypted with whichever configured key still fits and re-encrypted under the
first. Idempotent -- a value already under the primary key is rewritten to an
equivalent token -- so a re-run after an interruption is safe. ``--dry-run``
reports the counts without writing.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from onadata.apps.api.models.encrypted_recovery_device import EncryptedRecoveryCode
from onadata.apps.api.models.encrypted_totp_device import EncryptedTOTPDevice
from onadata.libs.utils.field_encryption import reencrypt_to_primary


class Command(BaseCommand):
    help = "Re-encrypt authenticator seeds and recovery codes under the primary key."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Count what would be re-encrypted without writing.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        seeds = self._rotate(EncryptedTOTPDevice.objects.all(), "encrypted_key", dry_run)
        codes = self._rotate(
            EncryptedRecoveryCode.objects.all(), "encrypted_code", dry_run
        )
        verb = "Would re-encrypt" if dry_run else "Re-encrypted"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {seeds} authenticator seed(s) and {codes} recovery code(s)."
            )
        )

    def _rotate(self, queryset, field, dry_run) -> int:
        count = 0
        with transaction.atomic():
            for row in queryset.iterator():
                if dry_run:
                    count += 1
                    continue
                setattr(row, field, reencrypt_to_primary(getattr(row, field)))
                row.save(update_fields=[field])
                count += 1
        return count
