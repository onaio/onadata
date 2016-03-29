from celery import task

from django.contrib.gis.geos import LineString
from django.contrib.gis.geos import Point
from django.contrib.gis.geos import Polygon
from django.contrib.gis.geos import GeometryCollection
from django.db import IntegrityError
from django.db import models

from lxml import etree

from onadata.apps.logger.models.osmdata import OsmData
from onadata.apps.logger.models.attachment import Attachment
from onadata.apps.logger.models.instance import Instance


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


def get_combined_osm(osm_list):
    """
    Combine osm xml form list of OsmData objects
    """
    xml = u""
    if (len(osm_list) and isinstance(osm_list, list)) \
            or isinstance(osm_list, models.QuerySet):
        osm = None
        for osm_data in osm_list:
            osm_xml = osm_data.xml
            _osm = _get_xml_obj(osm_xml)
            if _osm is None:
                continue

            if osm is None:
                osm = _osm
                continue

            for child in _osm.getchildren():
                osm.append(child)

        if osm is not None:
            xml = etree.tostring(osm, encoding='utf-8', xml_declaration=True)

    elif isinstance(osm_list, dict):
        if 'detail' in osm_list:
            xml = u'<error>' + osm_list['detail'] + '</error>'

    return xml


def parse_osm_ways(osm_xml, include_osm_id=False):
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

        tags = parse_osm_tags(way, include_osm_id)
        items.append({
            'osm_id': way.get('id'),
            'geom': geom,
            'tags': tags,
            'osm_type': 'way'
        })

    return items


def parse_osm_nodes(osm_xml, include_osm_id=False):
    """Converts an OSM XMl to a list of GEOSGeometry objects """
    items = []

    root = _get_xml_obj(osm_xml)

    for node in root.findall('node'):
        x, y = float(node.get('lon')), float(node.get('lat'))
        point = Point(x, y)
        tags = parse_osm_tags(node, include_osm_id)
        items.append({
            'osm_id': node.get('id'),
            'geom': point,
            'tags': tags,
            'osm_type': 'node'
        })

    return items


def parse_osm_tags(node, include_osm_id=False):
    """Retrieves all the tags from a osm xml node"""
    tags = {} if not include_osm_id else {node.tag + ':id': node.get('id')}
    for tag in node.findall('tag'):
        key, val = tag.attrib['k'], tag.attrib['v']
        if val == '' or val.upper() == 'FIXME':
            continue
        tags.update({key: val})

    return tags


def parse_osm(osm_xml, include_osm_id=False):
    ways = parse_osm_ways(osm_xml, include_osm_id)
    if ways:
        return ways

    nodes = parse_osm_nodes(osm_xml, include_osm_id)

    return nodes


@task()
def save_osm_data_async(instance_id):
    save_osm_data(instance_id)


def save_osm_data(instance_id):
    instance = Instance.objects.filter(pk=instance_id).first()
    osm_attachments = instance.attachments.filter(extension=Attachment.OSM) \
        if instance else None

    if instance and osm_attachments:
        xform = instance.xform
        fields = [f.get_abbreviated_xpath()
                  for f in xform.get_survey_elements_of_type('osm')]
        osm_filenames = {}
        for field in fields:
            filename = instance.json.get(field)
            if filename:
                osm_filenames.update({field: filename})

        for osm in osm_attachments:
                osm_xml = osm.media_file.read()
                filename = None
                field_name = None
                for k, v in osm_filenames.items():
                    fn = v.replace('.osm', '')
                    if osm.filename.startswith(fn):
                        filename = v
                        field_name = k
                        break

                if field_name is None:
                    continue
                filename = osm.filename if filename is None else filename
                osm_list = parse_osm(osm_xml, include_osm_id=True)
                for osmd in osm_list:
                    geom = GeometryCollection(osmd['geom'])
                    osm_id = osmd['osm_id']
                    osm_type = osmd['osm_type']
                    tags = osmd['tags']

                    try:
                        osm_data = OsmData(
                            instance=instance,
                            xml=osm_xml,
                            osm_id=osm_id,
                            osm_type=osm_type,
                            tags=tags,
                            geom=geom,
                            filename=filename,
                            field_name=field_name
                        )
                        osm_data.save()
                    except IntegrityError:
                        osm_data = OsmData.objects.get(
                            instance=instance,
                            field_name=field_name
                        )
                        osm_data.xml = osm_xml
                        osm_data.osm_id = osm_id
                        osm_data.osm_type = osm_type
                        osm_data.tags = tags
                        osm_data.geom = geom
                        osm_data.filename = filename
                        osm_data.save()


def osm_flat_dict(instance_id):
    osm_data = OsmData.objects.filter(instance=instance_id)
    tags = {}

    for osm in osm_data:
        for tag in osm.tags:
            for k, v in tag.iteritems():
                tags.update({"osm_{}".format(k):
                             v})

    return tags
