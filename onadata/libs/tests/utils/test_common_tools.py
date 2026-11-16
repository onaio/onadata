"""Tests for onadata.libs.utils.common_tools."""

from django.db import OperationalError
from django.test import SimpleTestCase

from onadata.libs.utils.common_tools import prefetch_first


class PrefetchFirstTestCase(SimpleTestCase):
    """Fetching the first item of a lazy iterable straight away."""

    def test_fetches_the_first_item_immediately(self):
        fetched = []

        def rows():
            for row in (1, 2, 3):
                fetched.append(row)
                yield row

        items = prefetch_first(rows())

        self.assertEqual(fetched, [1])
        self.assertEqual(list(items), [1, 2, 3])
        self.assertEqual(fetched, [1, 2, 3])

    def test_raises_an_error_from_the_first_fetch(self):
        def conflicting_rows():
            raise OperationalError("canceling statement due to conflict with recovery")
            yield  # pylint: disable=unreachable

        with self.assertRaises(OperationalError):
            prefetch_first(conflicting_rows())

    def test_keeps_falsy_items(self):
        self.assertEqual(list(prefetch_first([0, None, 2])), [0, None, 2])

    def test_returns_nothing_for_empty_input(self):
        self.assertEqual(list(prefetch_first([])), [])
