# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('logger', '0003_dataview_instances_with_geopoints'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectGroupObjectPermission',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False,
                                        auto_created=True, primary_key=True)),
                ('content_object', models.ForeignKey(
                    to='logger.Project', on_delete=models.CASCADE)),
                ('group', models.ForeignKey(to='auth.Group',
                    on_delete=models.CASCADE)),
                ('permission', models.ForeignKey(to='auth.Permission',
                    on_delete=models.CASCADE)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ProjectUserObjectPermission',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False,
                                        auto_created=True, primary_key=True)),
                ('content_object', models.ForeignKey(to='logger.Project',
                    on_delete=models.CASCADE)),
                ('permission', models.ForeignKey(to='auth.Permission',
                    on_delete=models.CASCADE)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL,
                    on_delete=models.CASCADE)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='projectuserobjectpermission',
            unique_together=set([('user', 'permission', 'content_object')]),
        ),
        migrations.AlterUniqueTogether(
            name='projectgroupobjectpermission',
            unique_together=set([('group', 'permission', 'content_object')]),
        ),
    ]
