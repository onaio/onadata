import unittest

from django.contrib.gis.geos import GEOSGeometry

from onadata.libs.utils.osm import parse_osm_nodes
from onadata.libs.utils.osm import parse_osm_ways
from onadata.libs.utils.osm import parse_osm

OSMWay = """
<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="OpenMapKit 0.7" user="theoutpost">
    <node id="-1943" lat="-11.202901601" lon="28.883830387" />
    <node id="-1946" lat="-11.202926082" lon="28.883944473" />
    <node id="-1945" lat="-11.202845645" lon="28.88396943" />
    <node id="-1944" lat="-11.202821164" lon="28.883858908" />
    <node id="-1943" lat="-11.202901601" lon="28.883830387" />
    <way id="-1942" action="modify">
        <nd ref="-1943" />
        <nd ref="-1946" />
        <nd ref="-1945" />
        <nd ref="-1944" />
        <nd ref="-1943" />
        <tag k="Shape_Area" v="0.00000000969" />
        <tag k="district_1" v="Mansa" />
        <tag k="manual_c_1" v="Targeted" />
        <tag k="OBJECTID" v="79621" />
        <tag k="rank_1" v="300.000000" />
        <tag k="province_1" v="Luapula" />
        <tag k="Shape_Leng" v="0.00039944548" />
        <tag k="psa_id_1" v="300 / 450" />
        <tag k="y" v="-11.20287380280" />
        <tag k="x3" v="28.88390064920" />
        <tag k="structur_1" v="450.000000" />
        <tag k="id" v="300 / 450_Mansa" />
        <tag k="spray_status" v="yes" />
    </way>
</osm>
"""
OSMNode = """
<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="OpenMapKit 0.12" user="theoutpost">
  <node id="-1" action="modify" lat="-9.24311382416424"
  lon="28.805980682373047">
    <tag k="spray_status" v="sprayed" />
  </node>
</osm>
"""  # noqa
# Faulty xml, the attribute action appears twice in the <node> tag
OSMNodeFaulty = """
<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="OpenMapKit 0.12" user="theoutpost">
  <node id="-1" action="modify" lat="-9.24311382416424"
  lon="28.805980682373047" action="modify">
    <tag k="spray_status" v="sprayed" />
  </node>
</osm>
"""  # noqa


class TestOSM(unittest.TestCase):
    def test_parse_osm(self):
        ways = parse_osm(OSMWay.strip())
        self.assertTrue(len(ways) > 0)
        node = ways[0]
        self.assertIsInstance(node['geom'], GEOSGeometry)

        nodes = parse_osm(OSMNode.strip())
        self.assertTrue(len(nodes) > 0)
        node = nodes[0]
        self.assertIsInstance(node['geom'], GEOSGeometry)

    def test_parse_osm_ways(self):
        ways = parse_osm_ways(OSMWay.strip())
        self.assertTrue(len(ways) > 0)
        node = ways[0]
        self.assertIsInstance(node['geom'], GEOSGeometry)

    def test_parse_osm_node(self):
        nodes = parse_osm_nodes(OSMNode.strip())
        self.assertTrue(len(nodes) > 0)
        node = nodes[0]
        self.assertIsInstance(node['geom'], GEOSGeometry)

    def test_parse_osm_node_faulty(self):
        nodes = parse_osm_nodes(OSMNodeFaulty.strip())
        self.assertTrue(len(nodes) > 0)
        node = nodes[0]
        self.assertIsInstance(node['geom'], GEOSGeometry)

    def test_parse_osm_tags(self):
        ways = parse_osm_ways(OSMWay.strip())
        self.assertTrue(len(ways) > 0)
        tags = ways[0]['tags']
        self.assertEqual(tags,
                         {'Shape_Area': '0.00000000969',
                          'district_1': 'Mansa',
                          'manual_c_1': 'Targeted',
                          'OBJECTID': '79621',
                          'rank_1': '300.000000',
                          'province_1': 'Luapula',
                          'Shape_Leng': '0.00039944548',
                          'psa_id_1': '300 / 450',
                          'y': '-11.20287380280',
                          'x3': '28.88390064920',
                          'structur_1': '450.000000',
                          'id': '300 / 450_Mansa',
                          'spray_status': 'yes'})

    def test_include_osm_id_in_tags(self):
        ways = parse_osm_ways(OSMWay.strip(), include_osm_id=True)
        self.assertTrue(len(ways) > 0)
        tags = ways[0]['tags']
        self.assertEqual(tags,
                         {'Shape_Area': '0.00000000969',
                          'district_1': 'Mansa',
                          'manual_c_1': 'Targeted',
                          'OBJECTID': '79621',
                          'rank_1': '300.000000',
                          'province_1': 'Luapula',
                          'Shape_Leng': '0.00039944548',
                          'psa_id_1': '300 / 450',
                          'way:id': '-1942',
                          'y': '-11.20287380280',
                          'x3': '28.88390064920',
                          'structur_1': '450.000000',
                          'id': '300 / 450_Mansa',
                          'spray_status': 'yes'})
