# pylint: skip-file
# Generated by Django 2.2.10 on 2020-07-13 12:14

from django.db import migrations
from onadata.libs.utils.common_tools import get_uuid


def generate_uuid_if_missing(apps, schema_editor):
    """
    Generate uuids for XForms without them
    """
    XForm = apps.get_model("logger", "XForm")

    for xform in XForm.objects.filter(uuid=""):
        xform.uuid = get_uuid()
        xform.save()


class Migration(migrations.Migration):

    dependencies = [
        ("logger", "0060_auto_20200305_0357"),
    ]

    operations = [migrations.RunPython(generate_uuid_if_missing)]
