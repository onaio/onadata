# -*- coding=utf-8 -*-
"""
OSM utility module.
"""
from __future__ import unicode_literals

import logging

from future.utils import iteritems

from django.contrib.gis.geos import (GeometryCollection, LineString, Point,
                                     Polygon)
from django.contrib.gis.geos.error import GEOSException
from django.db import IntegrityError, models, transaction

from celery import task
from lxml import etree

from onadata.apps.logger.models.attachment import Attachment
from onadata.apps.logger.models.instance import Instance
from onadata.apps.logger.models.osmdata import OsmData
from onadata.apps.restservice.signals import trigger_webhook


def _get_xml_obj(xml):
    if not isinstance(xml, bytes):
        xml = xml.strip().encode()
    try:
        return etree.fromstring(xml)  # pylint: disable=E1101
    except etree.XMLSyntaxError as e:  # pylint: disable=E1101
        if 'Attribute action redefined' in e.msg:
            xml = xml.replace(b'action="modify" ', b'')

            return _get_xml_obj(xml)


def _get_node(ref, root):
    point = None
    nodes = root.xpath('//node[@id="{}"]'.format(ref))
    if nodes:
        node = nodes[0]
        point = Point(float(node.get('lon')), float(node.get('lat')))

    return point


def get_combined_osm(osm_list):
    """
    Combine osm xml form list of OsmData objects
    """
    xml = ''
    if (osm_list and isinstance(osm_list, list)) \
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
            # pylint: disable=E1101
            return etree.tostring(osm, encoding='utf-8', xml_declaration=True)
    elif isinstance(osm_list, dict):
        if 'detail' in osm_list:
            xml = '<error>%s</error>' % osm_list['detail']
    return xml.encode('utf-8')


def parse_osm_ways(osm_xml, include_osm_id=False):
    """Converts an OSM XMl to a list of GEOSGeometry objects """
    items = []

    root = _get_xml_obj(osm_xml)

    for way in root.findall('way'):
        geom = None
        points = []
        for node in way.findall('nd'):
            points.append(_get_node(node.get('ref'), root))
        try:
            geom = Polygon(points)
        except GEOSException:
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
        point = Point(float(node.get('lon')), float(node.get('lat')))
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
    """
    Parses OSM XML and return a list of ways or nodes.
    """
    ways = parse_osm_ways(osm_xml, include_osm_id)
    if ways:
        return ways

    nodes = parse_osm_nodes(osm_xml, include_osm_id)

    return nodes


@task()
def save_osm_data_async(instance_id):
    """
    Async task for saving OSM data for the specified submission.
    """
    save_osm_data(instance_id)


def save_osm_data(instance_id):
    """
    Includes the OSM data in the specified submission json data.
    """
    instance = Instance.objects.filter(pk=instance_id).first()
    osm_attachments = instance.attachments.filter(extension=Attachment.OSM) \
        if instance else None

    if instance and osm_attachments:
        fields = [
            f.get_abbreviated_xpath()
            for f in instance.xform.get_survey_elements_of_type('osm')
        ]
        osm_filenames = {
            field: instance.json[field]
            for field in fields if field in instance.json
        }

        for osm in osm_attachments:
            try:
                osm_xml = osm.media_file.read()
            except IOError as e:
                logging.exception("IOError saving osm data: %s" % str(e))
                continue
            else:
                filename = None
                field_name = None
                for k, v in osm_filenames.items():
                    if osm.filename.startswith(v.replace('.osm', '')):
                        filename = v
                        field_name = k
                        break

                if field_name is None:
                    continue
                filename = osm.filename if filename is None else filename
                osm_list = parse_osm(osm_xml, include_osm_id=True)
                for osmd in osm_list:
                    try:
                        with transaction.atomic():
                            osm_data = OsmData(
                                instance=instance,
                                xml=osm_xml,
                                osm_id=osmd['osm_id'],
                                osm_type=osmd['osm_type'],
                                tags=osmd['tags'],
                                geom=GeometryCollection(osmd['geom']),
                                filename=filename,
                                field_name=field_name)
                            osm_data.save()
                    except IntegrityError:
                        with transaction.atomic():
                            osm_data = OsmData.objects.exclude(
                                xml=osm_xml).filter(
                                instance=instance,
                                field_name=field_name).first()
                            if osm_data:
                                osm_data.xml = osm_xml
                                osm_data.osm_id = osmd['osm_id']
                                osm_data.osm_type = osmd['osm_type']
                                osm_data.tags = osmd['tags']
                                osm_data.geom = GeometryCollection(
                                                    osmd['geom'])
                                osm_data.filename = filename
                                osm_data.save()
        instance.save()
        trigger_webhook.send(sender=instance.__class__, instance=instance)


def osm_flat_dict(instance_id):
    """
    Flat dict of OSM tags for the specified submission.

    Each key starts with 'osm_*'.
    """
    osm_data = OsmData.objects.filter(instance=instance_id)
    tags = {}

    for osm in osm_data:
        for tag in osm.tags:
            for (k, v) in iteritems(tag):
                tags.update({"osm_{}".format(k): v})

    return tags
