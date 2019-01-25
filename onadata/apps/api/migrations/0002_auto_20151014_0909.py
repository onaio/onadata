# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('api', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrgProfileGroupObjectPermission',
            fields=[
                ('id', models.AutoField(
                    verbose_name='ID', serialize=False, auto_created=True,
                    primary_key=True)),
                ('content_object',
                 models.ForeignKey(to='api.OrganizationProfile',
                    on_delete=models.CASCADE)),
                ('group', models.ForeignKey(
                    to='auth.Group',
                    on_delete=models.CASCADE)),
                ('permission', models.ForeignKey(
                    to='auth.Permission',
                     on_delete=models.CASCADE)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='OrgProfileUserObjectPermission',
            fields=[
                ('id', models.AutoField(
                    verbose_name='ID', serialize=False, auto_created=True,
                    primary_key=True)),
                ('content_object',
                 models.ForeignKey(
                    to='api.OrganizationProfile',
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
            name='orgprofileuserobjectpermission',
            unique_together=set([('user', 'permission', 'content_object')]),
        ),
        migrations.AlterUniqueTogether(
            name='orgprofilegroupobjectpermission',
            unique_together=set([('group', 'permission', 'content_object')]),
        ),
    ]
