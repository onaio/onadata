"""Tests for onadata.libs.utils.common_tools."""

import gc
import weakref

from django.db import OperationalError
from django.test import SimpleTestCase

from onadata.libs.test_utils.recovery_conflict import conflicting_rows
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

    def test_releases_the_first_item_once_it_is_read(self):
        class Batch:  # pylint: disable=too-few-public-methods
            """A weak-referenceable item."""

        first_refs = []

        def batches():
            first = Batch()
            first_refs.append(weakref.ref(first))
            yield first
            del first
            yield Batch()

        items = prefetch_first(batches())
        next(items)
        self.assertIsNotNone(first_refs[0]())

        next(items)
        gc.collect()

        self.assertIsNone(first_refs[0]())

    def test_raises_an_error_from_the_first_fetch(self):
        rows = conflicting_rows()

        with self.assertRaises(OperationalError):
            prefetch_first(rows)

    def test_keeps_falsy_items(self):
        self.assertEqual(list(prefetch_first([0, None, 2])), [0, None, 2])

    def test_returns_nothing_for_empty_input(self):
        self.assertEqual(list(prefetch_first([])), [])
