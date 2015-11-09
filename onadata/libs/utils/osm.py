from celery import task

from django.contrib.gis.geos import LineString
from django.contrib.gis.geos import Point
from django.contrib.gis.geos import Polygon
from django.contrib.gis.geos import GeometryCollection

from lxml import etree

from onadata.apps.logger.models.osmdata import OsmData
from onadata.apps.logger.models.attachment import Attachment


def get_combined_osm(files):
    """
    Combines a list of osm files
    :param files - list of osm file objects

    :return string: osm xml string of the combined files
    """
    def _parse_osm_file(f):
        try:
            return etree.parse(f)
        except:
            return None

    xml = u""
    if len(files) and isinstance(files, list):
        osm = None
        for f in files:
            _osm = _parse_osm_file(f)
            if _osm is None:
                continue

            if osm is None:
                osm = _osm
                continue

            for child in _osm.getroot().getchildren():
                osm.getroot().append(child)

        if osm:
            xml = etree.tostring(osm, encoding='utf-8', xml_declaration=True)

    elif isinstance(files, dict):
        if 'detail' in files:
            xml = u'<error>' + files['detail'] + '</error>'

    return xml


def _get_xml_obj(xml):
    if not isinstance(xml, bytes):
        xml = xml.strip().encode()
    try:
        return etree.fromstring(xml)
    except etree.XMLSyntaxError as e:
        if 'Attribute action redefined' in e.msg:
            xml = xml.replace(b'action="modify" ', b'')

            return _get_xml_obj(xml)


def _get_node(ref, root):
    point = None
    nodes = root.xpath('//node[@id="{}"]'.format(ref))
    if nodes:
        node = nodes[0]
        x, y = float(node.get('lon')), float(node.get('lat'))
        point = Point(x, y)

    return point


def parse_osm_ways(osm_xml):
    """Converts an OSM XMl to a list of GEOSGeometry objects """
    items = []

    root = _get_xml_obj(osm_xml)

    for way in root.findall('way'):
        geom = None
        points = []
        for nd in way.findall('nd'):
            points.append(_get_node(nd.get('ref'), root))
        try:
            geom = Polygon(points)
        except:
            geom = LineString(points)

        tags = parse_osm_tags(way)
        items.append({
            'osm_id': way.get('id'),
            'geom': geom,
            'tags': tags
        })

    return items


def parse_osm_nodes(osm_xml):
    """Converts an OSM XMl to a list of GEOSGeometry objects """
    items = []

    root = _get_xml_obj(osm_xml)

    for node in root.findall('node'):
        x, y = float(node.get('lon')), float(node.get('lat'))
        point = Point(x, y)
        tags = parse_osm_tags(node)
        items.append({
            'osm_id': node.get('id'),
            'geom': point,
            'tags': tags
        })

    return items


def parse_osm_tags(node):
    """Retrieves all the tags from a osm xml node"""
    tags = {}
    for tag in node.findall('tag'):
        key, val = tag.attrib['k'], tag.attrib['v']
        if val == '' or val.upper() == 'FIXME':
            continue
        tags.update({key: val})

    return tags


def parse_osm(osm_xml):
    ways = parse_osm_ways(osm_xml)
    if ways:
        return ways

    nodes = parse_osm_nodes(osm_xml)

    return nodes


@task()
def save_osm_data_async(parsed_instance):
    save_osm_data(parsed_instance)


def save_osm_data(parsed_instance):
    from onadata.apps.viewer.models.parsed_instance import ParsedInstance
    try:
        parsed_instance = ParsedInstance.objects.get(pk=parsed_instance)

        for osm in parsed_instance.instance.attachments.filter(
                extension=Attachment.OSM):
                osm_xml = osm.media_file.read()

                osm_list = parse_osm(osm_xml)
                for osmd in osm_list:
                    geom = GeometryCollection(osmd['geom'])
                    osm_id = osmd['osm_id']
                    tags = osmd['tags']

                    osm_data = OsmData(
                        instance=parsed_instance.instance,
                        xml=osm_xml,
                        osm_id=osm_id,
                        tags=tags,
                        geom=geom,
                        filename=osm.filename
                    )
                    osm_data.save()
    except ParsedInstance.DoesNotExist:
        pass


def osm_flat_dict(instance_id):
    osm_data = OsmData.objects.filter(instance=instance_id)
    tags = {}

    for osm in osm_data:
        for tag in osm.tags:
            for k, v in tag.iteritems():
                tags.update({"osm_{}".format(k):
                             v})

    return tags
