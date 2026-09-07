# -*- coding: utf-8 -*-
"""Manage the at-rest encryption of second-factor secrets.

Default action re-encrypts every authenticator seed and recovery code under the
current primary key. Roll a new key in at the front of
``TWO_FACTOR_FIELD_ENCRYPTION_KEYS``, run this command, then drop the old key:
every secret is decrypted with whichever configured key still fits and
re-encrypted under the first.

Keep the old key in the list until this command prints its completion counts --
only then drop it. Writes are committed in batches rather than one long
transaction, so a login is never blocked on the whole run and an interruption
leaves some secrets under the new key and some under the old. That mix is safe
because both keys are still configured and either decrypts, and re-running
finishes the rest (a value already under the primary key is simply rewritten to
an equivalent token). If a secret cannot be decrypted with any configured key --
the old key was dropped too early -- the command logs an error and stops rather
than skipping it silently; restore the key and re-run.

``--dry-run`` reports the rotation counts without writing.

``--verify`` decrypts every stored secret with the configured keys and reports
how many cannot be read, without writing -- a pre-deploy check that the keys
still fit the data. Exits non-zero if any secret fails.

``--purge-undecryptable`` deletes the devices whose secrets no configured key
can decrypt (recovery codes cascade with their device). Use it only after a key
is genuinely lost: the affected users fall back to password login and must
re-enrol, and the deleted ciphertext is unrecoverable. It prompts for
confirmation unless ``--noinput`` is given.
"""

import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from onadata.apps.api.models.encrypted_recovery_device import (
    EncryptedRecoveryCode,
    EncryptedRecoveryDevice,
)
from onadata.apps.api.models.encrypted_totp_device import EncryptedTOTPDevice
from onadata.libs.utils.field_encryption import (
    FieldEncryptionError,
    decrypt,
    reencrypt_to_primary,
)

logger = logging.getLogger(__name__)

#: Rows handled per committed transaction: small enough that a login is never
#: blocked on a large run, large enough to keep the round trips down.
BATCH_SIZE = 500


def _decryptable(value) -> bool:
    try:
        decrypt(value)
        return True
    except FieldEncryptionError:
        return False


class Command(BaseCommand):
    help = "Re-encrypt, verify, or purge second-factor secrets."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Count what would be re-encrypted without writing.",
        )
        parser.add_argument(
            "--verify",
            action="store_true",
            help="Check the configured keys decrypt existing secrets; write nothing.",
        )
        parser.add_argument(
            "--purge-undecryptable",
            action="store_true",
            help="Delete devices whose secrets no configured key can decrypt.",
        )
        parser.add_argument(
            "--noinput",
            action="store_true",
            help="Skip the confirmation prompt for --purge-undecryptable.",
        )

    def handle(self, *args, **options):
        if options["verify"]:
            self._verify_keys()
            return
        if options["purge_undecryptable"]:
            self._purge_undecryptable(options["noinput"])
            return
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

    def _verify_keys(self):
        seed_bad = self._count_undecryptable(
            EncryptedTOTPDevice.objects.all(), "encrypted_key"
        )
        code_bad = self._count_undecryptable(
            EncryptedRecoveryCode.objects.all(), "encrypted_code"
        )
        seeds = EncryptedTOTPDevice.objects.count()
        codes = EncryptedRecoveryCode.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"{seeds - seed_bad}/{seeds} authenticator seed(s) and "
                f"{codes - code_bad}/{codes} recovery code(s) decrypt with the "
                "configured keys."
            )
        )
        if seed_bad or code_bad:
            raise CommandError(
                f"{seed_bad} seed(s) and {code_bad} recovery code(s) cannot be "
                "decrypted with the configured keys."
            )

    def _count_undecryptable(self, queryset, field) -> int:
        bad = 0
        for row in queryset.iterator(chunk_size=BATCH_SIZE):
            if not _decryptable(getattr(row, field)):
                bad += 1
                logger.error(
                    "Cannot decrypt %s id=%s with the configured keys.",
                    queryset.model.__name__,
                    row.pk,
                )
        return bad

    def _purge_undecryptable(self, noinput: bool):
        seed_ids = [
            device.pk
            for device in EncryptedTOTPDevice.objects.iterator(chunk_size=BATCH_SIZE)
            if not _decryptable(device.encrypted_key)
        ]
        recovery_ids = {
            code.device_id
            for code in EncryptedRecoveryCode.objects.iterator(chunk_size=BATCH_SIZE)
            if not _decryptable(code.encrypted_code)
        }
        if not seed_ids and not recovery_ids:
            self.stdout.write(
                self.style.SUCCESS("No undecryptable devices found; nothing to purge.")
            )
            return

        self.stdout.write(
            f"{len(seed_ids)} authenticator device(s) and {len(recovery_ids)} "
            "recovery set(s) cannot be decrypted. Deleting them forces those users "
            "to re-enrol and cannot be undone."
        )
        if not noinput and input("Type 'yes' to delete them: ") != "yes":
            self.stdout.write("Aborted; nothing deleted.")
            return

        with transaction.atomic():
            EncryptedTOTPDevice.objects.filter(pk__in=seed_ids).delete()
            EncryptedRecoveryDevice.objects.filter(pk__in=recovery_ids).delete()
        logger.warning(
            "Purged %d undecryptable authenticator device(s) and %d recovery set(s).",
            len(seed_ids),
            len(recovery_ids),
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {len(seed_ids)} authenticator device(s) and "
                f"{len(recovery_ids)} recovery set(s)."
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
