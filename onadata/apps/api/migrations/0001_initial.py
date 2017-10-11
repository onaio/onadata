# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('logger', '0001_initial'),
        ('main', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('auth', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrganizationProfile',
            fields=[
                ('userprofile_ptr', models.OneToOneField(
                    parent_link=True, auto_created=True, primary_key=True,
                    serialize=False, to='main.UserProfile')),
                ('is_organization', models.BooleanField(default=True)),
                ('creator', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'permissions': (
                    ('can_add_xform',
                     'Can add/upload an xform to organization'),
                    ('view_organizationprofile',
                     'Can view organization profile')),
            },
            bases=('main.userprofile',),
        ),
        migrations.CreateModel(
            name='Team',
            fields=[
                ('group_ptr', models.OneToOneField(
                    parent_link=True, auto_created=True, primary_key=True,
                    serialize=False, to='auth.Group')),
                ('date_created', models.DateTimeField(
                    auto_now_add=True, null=True)),
                ('date_modified', models.DateTimeField(
                    auto_now=True, null=True)),
                ('created_by', models.ForeignKey(
                    related_name='team_creator', blank=True,
                    to=settings.AUTH_USER_MODEL, null=True)),
                ('organization',
                 models.ForeignKey(to=settings.AUTH_USER_MODEL)),
                ('projects', models.ManyToManyField(to='logger.Project')),
            ],
            options={
                'permissions': (('view_team', 'Can view team.'),),
            },
            bases=('auth.group',),
        ),
        migrations.CreateModel(
            name='TempToken',
            fields=[
                ('key', models.CharField(max_length=40, serialize=False,
                                         primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(related_name='_user',
                                              to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
