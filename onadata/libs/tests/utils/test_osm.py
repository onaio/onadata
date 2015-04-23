import os
import unittest

from onadata.libs.utils.osm import get_combined_osm


class TestOSM(unittest.TestCase):
    def test_get_combined_osm(self):
        filenames = ['osm1.osm', 'osm2.osm']
        files = [
            open(os.path.join(os.path.dirname(__file__), "fixtures", filename))
            for filename in filenames]
        path = os.path.join(os.path.dirname(__file__), "fixtures",
                            "combined.osm")
        with open(path) as f:
            osm = f.read()
            self.assertEqual(get_combined_osm(files), osm)
