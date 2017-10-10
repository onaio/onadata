# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('logger', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ColumnRename',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False,
                                        auto_created=True, primary_key=True)),
                ('xpath', models.CharField(unique=True, max_length=255)),
                ('column_name', models.CharField(max_length=32)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Export',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False,
                                        auto_created=True, primary_key=True)),
                ('created_on', models.DateTimeField(auto_now=True,
                                                    auto_now_add=True)),
                ('filename', models.CharField(max_length=255, null=True,
                                              blank=True)),
                ('filedir', models.CharField(max_length=255, null=True,
                                             blank=True)),
                ('export_type', models.CharField(
                    default=b'xls', max_length=10,
                    choices=[(b'xls', b'Excel'), (b'csv', b'CSV'),
                             (b'gdoc', b'GDOC'), (b'zip', b'ZIP'),
                             (b'kml', b'kml'), (b'csv_zip', b'CSV ZIP'),
                             (b'sav_zip', b'SAV ZIP'), (b'sav', b'SAV'),
                             (b'external', b'Excel'), ('osm', 'osm')])),
                ('task_id', models.CharField(max_length=255, null=True,
                                             blank=True)),
                ('time_of_last_submission',
                 models.DateTimeField(default=None, null=True)),
                ('internal_status', models.SmallIntegerField(default=0,
                                                             max_length=1)),
                ('export_url', models.URLField(default=None, null=True)),
                ('xform', models.ForeignKey(to='logger.XForm')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ParsedInstance',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False,
                                        auto_created=True, primary_key=True)),
                ('start_time', models.DateTimeField(null=True)),
                ('end_time', models.DateTimeField(null=True)),
                ('lat', models.FloatField(null=True)),
                ('lng', models.FloatField(null=True)),
                ('instance',
                 models.OneToOneField(related_name='parsed_instance',
                                      to='logger.Instance')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='export',
            unique_together=set([('xform', 'filename')]),
        ),
        migrations.CreateModel(
            name='DataDictionary',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('logger.xform',),
        ),
    ]
