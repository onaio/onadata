from lxml import etree


def get_combined_osm(files):
    """
    Combines a list of osm files
    :param files - list of osm file objects

    :return string: osm xml string of the combined files
    """
    xml = u""
    if len(files):
        first = etree.parse(files[0])

        for f in files[1:]:
            osm_root = etree.parse(f).getroot()
            for child in osm_root.getchildren():
                first.getroot().append(child)

        xml = etree.tostring(first, encoding='utf-8', xml_declaration=True)

    return xml
