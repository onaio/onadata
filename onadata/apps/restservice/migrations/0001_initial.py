# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('logger', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='RestService',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('service_url', models.URLField(verbose_name='Service URL')),
                ('name', models.CharField(max_length=50, choices=[('f2dhis2', 'f2dhis2'), ('generic_json', 'JSON POST'), ('generic_xml', 'XML POST'), ('bamboo', 'bamboo'), ('textit', 'TextIt POST')])),
                ('xform', models.ForeignKey(to='logger.XForm')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='restservice',
            unique_together=set([('service_url', 'xform', 'name')]),
        ),
    ]
