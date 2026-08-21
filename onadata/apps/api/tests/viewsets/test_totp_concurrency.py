# -*- coding: utf-8 -*-
"""Concurrency tests for one-time-code verification.

Threads here stand in for the deployment's uWSGI workers (``--workers 30
--threads 1``): what matters is several connections racing the same row, and
threads reproduce that without the cost of spawning processes. If anything
they understate it -- the GIL serialises bytecode that separate workers run
in parallel.

``TransactionTestCase`` rather than ``TestCase``: the usual per-test
transaction is never committed, so a second connection would not see the
fixture at all.
"""
import threading

from django.contrib.auth.models import User
from django.db import connection
from django.test import TransactionTestCase, override_settings

from django_otp.oath import totp
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

from onadata.apps.api.viewsets.totp_viewset import (
    RECOVERY_DEVICE_NAME,
    TOTP_DEVICE_NAME,
    _verify_recovery,
    _verify_totp,
)

CONCURRENT = 8
RECOVERY_CODE = "onceonly"


@override_settings(ENABLE_TWO_FACTOR=True)
class RecoveryCodeConcurrencyTestCase(TransactionTestCase):
    """A recovery code is single-use, including against itself."""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            "raceprobe", "race@example.com", "pw-9F3kz"
        )
        device = StaticDevice.objects.create(
            user=self.user, name=RECOVERY_DEVICE_NAME, confirmed=True
        )
        StaticToken.objects.create(device=device, token=RECOVERY_CODE)

    def _spend_concurrently(self):
        barrier = threading.Barrier(CONCURRENT)
        results = []
        guard = threading.Lock()

        def worker():
            try:
                barrier.wait(timeout=10)
                verified = _verify_recovery(self.user, RECOVERY_CODE)
                with guard:
                    results.append(verified)
            finally:
                # Each thread holds its own connection; leaking them exhausts
                # the pool and hangs whatever runs next.
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(CONCURRENT)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        return results

    def test_one_code_is_spent_once_however_many_callers_race(self):
        results = self._spend_concurrently()

        self.assertEqual(
            len(results), CONCURRENT, "a worker did not finish -- lock contention?"
        )
        # The positive half matters as much as the negative: a guard that
        # refused everyone would also report one-or-fewer successes.
        self.assertEqual(
            sum(results),
            1,
            f"the code was accepted {sum(results)} times; it is single-use",
        )
        self.assertFalse(
            StaticToken.objects.filter(token=RECOVERY_CODE).exists(),
            "the spent code should be gone",
        )


@override_settings(ENABLE_TWO_FACTOR=True)
class TotpCodeConcurrencyTestCase(TransactionTestCase):
    """One authenticator code buys one verification, not one per worker."""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            "totpraceprobe", "totprace@example.com", "pw-9F3kz"
        )
        self.device = TOTPDevice.objects.create(
            user=self.user, name=TOTP_DEVICE_NAME, confirmed=True
        )

    def test_one_code_verifies_once_however_many_callers_race(self):
        """``last_t`` is the replay guard, and it is read-modify-write.

        Without the row lock every racing worker reads the same ``last_t``,
        so a captured code authorises as many step-up grants as there are
        workers to spend it.
        """
        code = f"{totp(self.device.bin_key, self.device.step, self.device.t0):06d}"
        barrier = threading.Barrier(CONCURRENT)
        results = []
        guard = threading.Lock()

        def worker():
            try:
                barrier.wait(timeout=10)
                verified = _verify_totp(self.user, code)
                with guard:
                    results.append(verified)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(CONCURRENT)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        self.assertEqual(len(results), CONCURRENT, "a worker did not finish")
        self.assertEqual(
            sum(results),
            1,
            f"the code verified {sum(results)} times; one code, one use",
        )
