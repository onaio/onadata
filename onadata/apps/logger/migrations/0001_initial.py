# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields
import onadata.apps.logger.models.xform
import django.contrib.gis.db.models.fields
from django.conf import settings
import onadata.apps.logger.models.attachment
import taggit.managers


class Migration(migrations.Migration):

    dependencies = [
        ('taggit', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Attachment',
            fields=[
                ('id', models.AutoField(
                    verbose_name='ID', serialize=False, auto_created=True,
                    primary_key=True)),
                ('media_file', models.FileField(
                    max_length=255,
                    upload_to=onadata.apps.logger.models.attachment.upload_to)
                 ),
                ('mimetype', models.CharField(
                    default=b'', max_length=50, blank=True)),
                ('extension',
                 models.CharField(default='non', max_length=10, db_index=True)
                 ),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='DataView',
            fields=[
                ('id', models.AutoField(
                    verbose_name='ID', serialize=False, auto_created=True,
                    primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('columns', jsonfield.fields.JSONField()),
                ('query', jsonfield.fields.JSONField(default={}, blank=True)),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('date_modified', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Data View',
                'verbose_name_plural': 'Data Views',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Instance',
            fields=[
                ('id', models.AutoField(
                    verbose_name='ID', serialize=False, auto_created=True,
                    primary_key=True)),
                ('json', jsonfield.fields.JSONField(default={})),
                ('xml', models.TextField()),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('date_modified', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(default=None, null=True)),
                ('status', models.CharField(default='submitted_via_web',
                                            max_length=20)),
                ('uuid', models.CharField(default='', max_length=249)),
                ('version', models.CharField(max_length=255, null=True)),
                ('geom',
                 django.contrib.gis.db.models.fields.GeometryCollectionField(
                    srid=4326, null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='InstanceHistory',
            fields=[
                ('id', models.AutoField(
                    verbose_name='ID', serialize=False, auto_created=True,
                    primary_key=True)),
                ('xml', models.TextField()),
                ('uuid', models.CharField(default='', max_length=249)),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('date_modified', models.DateTimeField(auto_now=True)),
                ('xform_instance',
                 models.ForeignKey(related_name='submission_history',
                                   to='logger.Instance')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Note',
            fields=[
                ('id', models.AutoField(
                    verbose_name='ID', serialize=False, auto_created=True,
                    primary_key=True)),
                ('note', models.TextField()),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('date_modified', models.DateTimeField(auto_now=True)),
                ('instance',
                 models.ForeignKey(related_name='notes', to='logger.Instance')
                 ),
            ],
            options={
                'permissions': (('view_note', 'View note'),),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.AutoField(
                    verbose_name='ID', serialize=False, auto_created=True,
                    primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('metadata', jsonfield.fields.JSONField(blank=True)),
                ('shared', models.BooleanField(default=False)),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('date_modified', models.DateTimeField(auto_now=True)),
                ('created_by',
                 models.ForeignKey(related_name='project_owner',
                                   to=settings.AUTH_USER_MODEL)),
                ('organization', models.ForeignKey(
                    related_name='project_org', to=settings.AUTH_USER_MODEL)),
                ('tags',
                 taggit.managers.TaggableManager(
                    to='taggit.Tag', through='taggit.TaggedItem',
                    help_text='A comma-separated list of tags.',
                    verbose_name='Tags')),
                ('user_stars',
                 models.ManyToManyField(related_name='project_stars',
                                        to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'permissions': (
                    ('view_project', 'Can view project'),
                    ('add_project_xform', 'Can add xform to project'),
                    ('report_project_xform',
                     'Can make submissions to the project'),
                    ('transfer_project',
                     'Can transfer project to different owner'),
                    ('can_export_project_data', 'Can export data in project')),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SurveyType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False,
                                        auto_created=True, primary_key=True)),
                ('slug', models.CharField(unique=True, max_length=100)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Widget',
            fields=[
                ('id', models.AutoField(
                    verbose_name='ID', serialize=False, auto_created=True,
                    primary_key=True)),
                ('object_id', models.PositiveIntegerField()),
                ('widget_type',
                 models.CharField(default=b'charts', max_length=25,
                                  choices=[(b'charts', b'Charts')])),
                ('view_type', models.CharField(max_length=50)),
                ('column', models.CharField(max_length=50)),
                ('group_by',
                 models.CharField(default=None, max_length=50, null=True,
                                  blank=True)),
                ('title',
                 models.CharField(default=None, max_length=50, null=True,
                                  blank=True)),
                ('description',
                 models.CharField(default=None, max_length=255,
                                  null=True, blank=True)),
                ('key',
                 models.CharField(unique=True, max_length=32, db_index=True)),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('date_modified', models.DateTimeField(auto_now=True)),
                ('content_type',
                 models.ForeignKey(to='contenttypes.ContentType')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='XForm',
            fields=[
                ('id', models.AutoField(
                    verbose_name='ID', serialize=False, auto_created=True,
                    primary_key=True)),
                ('xls',
                 models.FileField(
                    null=True,
                    upload_to=onadata.apps.logger.models.xform.upload_to)),
                ('json', models.TextField(default='')),
                ('description', models.TextField(default='', null=True,
                                                 blank=True)),
                ('xml', models.TextField()),
                ('require_auth', models.BooleanField(default=False)),
                ('shared', models.BooleanField(default=False)),
                ('shared_data', models.BooleanField(default=False)),
                ('downloadable', models.BooleanField(default=True)),
                ('allows_sms', models.BooleanField(default=False)),
                ('encrypted', models.BooleanField(default=False)),
                ('sms_id_string',
                 models.SlugField(default=b'', verbose_name='SMS ID',
                                  max_length=100, editable=False)),
                ('id_string',
                 models.SlugField(verbose_name='ID', max_length=100,
                                  editable=False)),
                ('title', models.CharField(max_length=255, editable=False)),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('date_modified', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(null=True, blank=True)),
                ('last_submission_time',
                 models.DateTimeField(null=True, blank=True)),
                ('has_start_time', models.BooleanField(default=False)),
                ('uuid', models.CharField(default='', max_length=32)),
                ('bamboo_dataset',
                 models.CharField(default='', max_length=60)),
                ('instances_with_geopoints',
                 models.BooleanField(default=False)),
                ('instances_with_osm', models.BooleanField(default=False)),
                ('num_of_submissions', models.IntegerField(default=0)),
                ('version',
                 models.CharField(max_length=255, null=True, blank=True)),
                ('created_by',
                 models.ForeignKey(blank=True, to=settings.AUTH_USER_MODEL,
                                   null=True)),
                ('project', models.ForeignKey(to='logger.Project')),
                ('tags',
                 taggit.managers.TaggableManager(
                    to='taggit.Tag', through='taggit.TaggedItem',
                    help_text='A comma-separated list of tags.',
                    verbose_name='Tags')),
                ('user',
                 models.ForeignKey(related_name='xforms',
                                   to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
                'ordering': ('id_string',),
                'verbose_name': 'XForm',
                'verbose_name_plural': 'XForms',
                'permissions': (
                    ('view_xform', 'Can view associated data'),
                    ('report_xform', 'Can make submissions to the form'),
                    ('move_xform', 'Can move form between projects'),
                    ('transfer_xform', 'Can transfer form ownership.'),
                    ('can_export_xform_data', 'Can export form data')),
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='xform',
            unique_together=set(
                [('user', 'id_string', 'project'),
                 ('user', 'sms_id_string', 'project')]),
        ),
        migrations.AlterUniqueTogether(
            name='project',
            unique_together=set([('name', 'organization')]),
        ),
        migrations.AddField(
            model_name='instance',
            name='survey_type',
            field=models.ForeignKey(to='logger.SurveyType'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='instance',
            name='tags',
            field=taggit.managers.TaggableManager(
                to='taggit.Tag', through='taggit.TaggedItem',
                help_text='A comma-separated list of tags.',
                verbose_name='Tags'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='instance',
            name='user',
            field=models.ForeignKey(
                related_name='instances', to=settings.AUTH_USER_MODEL,
                null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='instance',
            name='xform',
            field=models.ForeignKey(related_name='instances',
                                    to='logger.XForm', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='dataview',
            name='project',
            field=models.ForeignKey(to='logger.Project'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='dataview',
            name='xform',
            field=models.ForeignKey(to='logger.XForm'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='attachment',
            name='instance',
            field=models.ForeignKey(related_name='attachments',
                                    to='logger.Instance'),
            preserve_default=True,
        ),
    ]
