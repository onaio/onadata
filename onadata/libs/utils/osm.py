from lxml import etree


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
