# -*- coding: utf-8 -*-
"""
Factory utility functions.
"""
# This factory is not the same as the others, and doesn't use
# django-factories but it mimics their functionality...
from datetime import timedelta

from pyxform import Survey
from pyxform.builder import create_survey_element_from_dict

from onadata.apps.logger.models import Instance, XForm

XFORM_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.000"
ONE_HOUR = timedelta(0, 3600)


def _load_registration_survey_object():
    """
    Loads a registration survey with all the values necessary
    to register a surveyor.
    """
    survey = Survey(name="registration", id_string="registration")
    survey.add_child(
        create_survey_element_from_dict(
            {"type": "text", "name": "name", "label": "Name"}
        )
    )
    survey.add_child(
        create_survey_element_from_dict({"type": "start time", "name": "start"})
    )
    survey.add_child(
        create_survey_element_from_dict({"type": "end time", "name": "end"})
    )
    survey.add_child(
        create_survey_element_from_dict({"type": "imei", "name": "device_id"})
    )

    return survey


def _load_simple_survey_object():
    """
    Returns a "watersimple" survey object,
    complete with questions.
    """
    survey = Survey(name="WaterSimple", id_string="WaterSimple")
    survey.add_child(
        create_survey_element_from_dict(
            {
                "hint": {"English": "What is this point named?"},
                "label": {"English": "Water Point Name"},
                "type": "text",
                "name": "name",
            }
        )
    )
    survey.add_child(
        create_survey_element_from_dict(
            {
                "hint": {"English": "How many people use this every month?"},
                "label": {"English": "Monthly Usage"},
                "name": "users_per_month",
                "type": "integer",
            }
        )
    )
    survey.add_child(
        create_survey_element_from_dict(
            {"type": "gps", "name": "geopoint", "label": {"English": "Location"}}
        )
    )
    survey.add_child(
        create_survey_element_from_dict({"type": "imei", "name": "device_id"})
    )
    survey.add_child(
        create_survey_element_from_dict({"type": "start time", "name": "start"})
    )
    survey.add_child(
        create_survey_element_from_dict({"type": "end time", "name": "end"})
    )

    return survey


class XFormManagerFactory:
    """XForm manager factory."""

    def create_registration_xform(self):
        """
        Calls 'get_registration_xform', saves the result, and returns.
        """
        xform = self.get_registration_xform()
        xform.save()

        return xform

    def get_registration_xform(self):
        """
        Gets a registration xform. (currently loaded in from fixture)
        Returns it without saving.
        """
        reg_xform = _load_registration_survey_object()

        return XForm(xml=reg_xform.to_xml())

    def create_registration_instance(self, custom_values=None):
        """Create registration instance."""
        custom_values = {} if custom_values is None else custom_values
        i = self.get_registration_instance(custom_values)
        i.save()
        return i

    def get_registration_instance(self, custom_values=None):
        """
        1. Checks to see if the registration form has been created alread.
           If not, it loads it in.
        2. Loads a registration instance.
        """
        custom_values = {} if custom_values is None else custom_values
        registration_xforms = XForm.objects.filter(title="registration")
        if registration_xforms.count() == 0:
            xform = self.create_registration_xform()
        else:
            xform = registration_xforms[0]

        values = {
            "device_id": "12345",
            "start": "2011-01-01T09:50:06.966",
            "end": "2011-01-01T09:53:22.965",
        }

        if "start" in custom_values:
            start = custom_values["start"]
            custom_values["start"] = start.strftime(XFORM_TIME_FORMAT)

            # if no end_time is specified, defaults to 1 hour
            values["end"] = (start + ONE_HOUR).strftime(XFORM_TIME_FORMAT)

        if "end" in custom_values:
            custom_values["end"] = custom_values["end"].strftime(XFORM_TIME_FORMAT)

        values.update(custom_values)

        reg_xform = _load_registration_survey_object()
        reg_instance = reg_xform.instantiate()
        # pylint: disable=protected-access
        reg_instance._id = xform.id_string

        for key, value in values.items():
            reg_instance.answer(name=key, value=value)

        instance_xml = reg_instance.to_xml()

        return Instance(xml=instance_xml)

    def create_simple_xform(self):
        """Creates and returns xform."""
        xform = self.get_simple_xform()
        xform.save()

        return xform

    def get_simple_xform(self):
        """Returns a simple xform."""
        survey_object = _load_simple_survey_object()
        return XForm(xml=survey_object.to_xml())

    def get_simple_instance(self, custom_values=None):
        """Returns a simple submission instance."""
        custom_values = {} if custom_values is None else custom_values
        simple_xforms = XForm.objects.filter(title="WaterSimple")
        if simple_xforms.count() == 0:
            xform = self.create_simple_xform()
        else:
            xform = simple_xforms[0]

        # these values can be overridden with custom values
        values = {
            "device_id": "12345",
            "start": "2011-01-01T09:50:06.966",
            "end": "2011-01-01T09:53:22.965",
            "geopoint": "40.783594633609184 -73.96436698913574 300.0 4.0",
        }

        if "start" in custom_values:
            start = custom_values["start"]
            custom_values["start"] = start.strftime(XFORM_TIME_FORMAT)

            # if no end_time is specified, defaults to 1 hour
            values["end"] = (start + ONE_HOUR).strftime(XFORM_TIME_FORMAT)

        if "end" in custom_values:
            custom_values["end"] = custom_values["end"].strftime(XFORM_TIME_FORMAT)

        values.update(custom_values)

        water_simple_survey = _load_simple_survey_object()
        simple_survey = water_simple_survey.instantiate()

        for key, value in values.items():
            simple_survey.answer(name=key, value=value)

        # setting the id_string so that it doesn't end up
        # with the timestamp of the new survey object
        # pylint: disable=protected-access
        simple_survey._id = xform.id_string

        instance_xml = simple_survey.to_xml()

        return Instance(xml=instance_xml)
