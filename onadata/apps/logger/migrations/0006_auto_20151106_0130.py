# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields
import django.contrib.gis.db.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('logger', '0005_auto_20151015_0758'),
    ]

    operations = [
        migrations.CreateModel(
            name='OsmData',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False,
                                        auto_created=True, primary_key=True)),
                ('xml', models.TextField()),
                ('osm_id', models.CharField(max_length=10)),
                ('tags', jsonfield.fields.JSONField(default={})),
                ('geom',
                 django.contrib.gis.db.models.fields.GeometryCollectionField(
                    srid=4326)),
                ('filename', models.CharField(max_length=255)),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('date_modified', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(default=None, null=True)),
                ('instance', models.ForeignKey(related_name='osm_data',
                                               to='logger.Instance')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterModelOptions(
            name='xform',
            options={
                'ordering': ('id_string',), 'verbose_name': 'XForm',
                'verbose_name_plural': 'XForms',
                'permissions': (
                    ('view_xform', 'Can view associated data'),
                    ('report_xform', 'Can make submissions to the form'),
                    ('move_xform', 'Can move form between projects'),
                    ('transfer_xform', 'Can transfer form ownership.'),
                    ('can_export_xform_data', 'Can export form data'),
                    ('delete_submission', 'Can delete submissions from form')
                    )},
        ),
    ]
