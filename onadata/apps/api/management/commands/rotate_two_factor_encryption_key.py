# -*- coding: utf-8 -*-
"""Re-encrypt second-factor secrets under the current primary key.

Roll a new key in at the front of ``TWO_FACTOR_FIELD_ENCRYPTION_KEYS``, run this
command, then drop the old key: every authenticator seed and recovery code is
decrypted with whichever configured key still fits and re-encrypted under the
first.

Keep the old key in the list until this command prints its completion counts --
only then drop it. Writes are committed in batches rather than one long
transaction, so a login is never blocked on the whole run and an interruption
leaves some secrets under the new key and some under the old. That mix is safe
because both keys are still configured and either decrypts, and re-running
finishes the rest (a value already under the primary key is simply rewritten to
an equivalent token). If a secret cannot be decrypted with any configured key --
the old key was dropped too early -- the command logs an error and stops rather
than skipping it silently; restore the key and re-run. ``--dry-run`` reports the
counts without writing.
"""

import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from onadata.apps.api.models.encrypted_recovery_device import EncryptedRecoveryCode
from onadata.apps.api.models.encrypted_totp_device import EncryptedTOTPDevice
from onadata.libs.utils.field_encryption import (
    FieldEncryptionError,
    reencrypt_to_primary,
)

logger = logging.getLogger(__name__)

#: Rows re-encrypted per committed transaction: small enough that a login is
#: never blocked on a large run, large enough to keep the round trips down.
BATCH_SIZE = 500


class Command(BaseCommand):
    help = "Re-encrypt authenticator seeds and recovery codes under the primary key."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Count what would be re-encrypted without writing.",
        )

    def handle(self, *args, **options):
        if options["dry_run"]:
            seeds = EncryptedTOTPDevice.objects.count()
            codes = EncryptedRecoveryCode.objects.count()
            self._report("Would re-encrypt", seeds, codes)
            return

        logger.info("Two-factor key rotation started.")
        seeds = self._rotate(EncryptedTOTPDevice.objects.all(), "encrypted_key")
        codes = self._rotate(EncryptedRecoveryCode.objects.all(), "encrypted_code")
        logger.info(
            "Two-factor key rotation finished: %d seed(s), %d recovery code(s).",
            seeds,
            codes,
        )
        self._report("Re-encrypted", seeds, codes)

    def _report(self, verb, seeds, codes):
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {seeds} authenticator seed(s) and {codes} recovery code(s)."
            )
        )

    def _rotate(self, queryset, field) -> int:
        rotated = 0
        batch = []
        for row in queryset.iterator(chunk_size=BATCH_SIZE):
            try:
                setattr(row, field, reencrypt_to_primary(getattr(row, field)))
            except FieldEncryptionError as exc:
                logger.error(
                    "Cannot decrypt %s id=%s during rotation; the old key may "
                    "have been dropped before this run finished. Restore it and "
                    "re-run. %d row(s) already re-encrypted.",
                    queryset.model.__name__,
                    row.pk,
                    rotated,
                )
                raise CommandError(
                    "A second-factor secret could not be decrypted with any "
                    "configured key; rotation stopped. Restore the previous key "
                    "and re-run."
                ) from exc
            batch.append(row)
            if len(batch) >= BATCH_SIZE:
                rotated += self._flush(batch, field)
                batch = []
        if batch:
            rotated += self._flush(batch, field)
        return rotated

    def _flush(self, rows, field) -> int:
        with transaction.atomic():
            for row in rows:
                row.save(update_fields=[field])
        return len(rows)
