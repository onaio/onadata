# -*- coding: utf-8 -*-
"""
ODK Collect/Briefcase XForm instances folder traversal.
"""
import os
import glob
import re


# pylint: disable=too-many-instance-attributes
class XFormInstanceFS:
    """A class to traverse an ODK Collect/Briefcase XForm instances folder."""

    def __init__(self, filepath):
        self.path = filepath
        self.directory, self.filename = os.path.split(self.path)
        self.xform_id = re.sub(".xml", "", self.filename)
        self._photos = []
        self._osm = []
        self._metadata_directory = ""
        self._xml = ""

    @property
    def photos(self):
        """Returns all .jpg file paths."""
        if not getattr(self, "_photos"):
            available_photos = glob.glob(os.path.join(self.directory, "*.jpg"))
            for photo_path in available_photos:
                _pdir, photo = os.path.split(photo_path)
                if self.xml.find(photo) > 0:
                    self._photos.append(photo_path)
        return self._photos

    @property
    def osm(self):
        """Returns all .osm file paths."""
        if not getattr(self, "_osm"):
            available_osm = glob.glob(os.path.join(self.directory, "*.osm"))
            for osm_path in available_osm:
                _pdir, osm = os.path.split(osm_path)
                if self.xml.find(osm) > 0:
                    self._osm.append(osm_path)
        return self._osm

    @property
    def metadata_directory(self):
        """Returns the metadata directory."""
        if not getattr(self, "_metadata_directory"):
            instances_dir = os.path.join(self.directory, "..", "..", "instances")
            metadata_directory = os.path.join(self.directory, "..", "..", "metadata")
            if os.path.exists(instances_dir) and os.path.exists(metadata_directory):
                self._metadata_directory = os.path.abspath(metadata_directory)
        return self._metadata_directory

    @property
    def xml(self):
        """Returns the submission XML"""
        if not getattr(self, "_xml"):
            with open(self.path, "r", encoding="utf-8") as xml_submission_file:
                self._xml = xml_submission_file.read()
        return self._xml

    @classmethod
    def is_valid_instance(cls, filepath):
        """Returns True if the XML at ``filepath`` is a valid XML file."""
        if not filepath.endswith(".xml"):
            return False
        with open(filepath, "r", encoding="utf-8") as xml_file:
            fxml = xml_file.read()
            if not fxml.strip().startswith("<?xml"):
                return False
        return True

    def __str__(self):
        return f"<XForm XML: {self.xform_id}>"
