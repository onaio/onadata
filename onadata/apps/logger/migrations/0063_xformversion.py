# Generated by Django 2.2.16 on 2021-03-01 14:01

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('logger', '0062_auto_20210202_0248'),
    ]

    operations = [
        migrations.CreateModel(
            name='XFormVersion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('xls', models.FileField(upload_to='')),
                ('version', models.CharField(max_length=100)),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('date_modified', models.DateTimeField(auto_now=True)),
                ('xml', models.TextField()),
                ('json', models.TextField()),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('xform', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='versions', to='logger.XForm')),
            ],
            options={
                'unique_together': {('xform', 'version')},
            },
        ),
    ]
