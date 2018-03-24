import unittest

from onadata.libs.data import statistics as stats


class TestStatistics(unittest.TestCase):
    def test_get_mean(self):
        values = [1, 2, 3, 2, 5, 5]
        result = stats.get_mean(values)
        self.assertEqual(result, 3)

    def test_get_median(self):
        values = [1, 2, 3, 2, 5, 5]
        result = stats.get_median(values)
        self.assertEqual(result, 2.5)
