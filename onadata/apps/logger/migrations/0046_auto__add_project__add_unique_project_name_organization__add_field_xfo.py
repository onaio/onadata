# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Removing unique constraint on 'XForm', fields ['user', 'sms_id_string']
        db.delete_unique(u'logger_xform', ['user_id', 'sms_id_string'])

        # Removing unique constraint on 'XForm', fields ['user', 'id_string']
        db.delete_unique(u'logger_xform', ['user_id', 'id_string'])

        # Adding model 'Project'
        db.create_table(u'logger_project', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('metadata', self.gf('jsonfield.fields.JSONField')(blank=True)),
            ('organization', self.gf('django.db.models.fields.related.ForeignKey')(related_name='project_organization', to=orm['auth.User'])),
            ('created_by', self.gf('django.db.models.fields.related.ForeignKey')(related_name='project_creator', to=orm['auth.User'])),
            ('shared', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('date_created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('date_modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
        ))
        db.send_create_signal('logger', ['Project'])

        # Adding M2M table for field user_stars on 'Project'
        m2m_table_name = db.shorten_name(u'logger_project_user_stars')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('project', models.ForeignKey(orm['logger.project'], null=False)),
            ('user', models.ForeignKey(orm[u'auth.user'], null=False))
        ))
        db.create_unique(m2m_table_name, ['project_id', 'user_id'])

        # Adding unique constraint on 'Project', fields ['name', 'organization']
        db.create_unique(u'logger_project', ['name', 'organization_id'])

        # Adding field 'XForm.project'
        db.add_column(u'logger_xform', 'project',
                      self.gf('django.db.models.fields.related.ForeignKey')(default=1, to=orm['logger.Project']),
                      keep_default=False)

        # Adding unique constraint on 'XForm', fields ['user', 'id_string', 'project']
        db.create_unique(u'logger_xform', ['user_id', 'id_string', 'project_id'])

        # Adding unique constraint on 'XForm', fields ['user', 'sms_id_string', 'project']
        db.create_unique(u'logger_xform', ['user_id', 'sms_id_string', 'project_id'])


    def backwards(self, orm):
        # Removing unique constraint on 'XForm', fields ['user', 'sms_id_string', 'project']
        db.delete_unique(u'logger_xform', ['user_id', 'sms_id_string', 'project_id'])

        # Removing unique constraint on 'XForm', fields ['user', 'id_string', 'project']
        db.delete_unique(u'logger_xform', ['user_id', 'id_string', 'project_id'])

        # Removing unique constraint on 'Project', fields ['name', 'organization']
        db.delete_unique(u'logger_project', ['name', 'organization_id'])

        # Deleting model 'Project'
        db.delete_table(u'logger_project')

        # Removing M2M table for field user_stars on 'Project'
        db.delete_table(db.shorten_name(u'logger_project_user_stars'))

        # Deleting field 'XForm.project'
        db.delete_column(u'logger_xform', 'project_id')

        # Adding unique constraint on 'XForm', fields ['user', 'id_string']
        db.create_unique(u'logger_xform', ['user_id', 'id_string'])

        # Adding unique constraint on 'XForm', fields ['user', 'sms_id_string']
        db.create_unique(u'logger_xform', ['user_id', 'sms_id_string'])


    models = {
        u'auth.group': {
            'Meta': {'object_name': 'Group'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'auth.permission': {
            'Meta': {'ordering': "(u'content_type__app_label', u'content_type__model', u'codename')", 'unique_together': "((u'content_type', u'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        u'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Group']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Permission']"}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'logger.attachment': {
            'Meta': {'object_name': 'Attachment'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instance': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'attachments'", 'to': "orm['logger.Instance']"}),
            'media_file': ('django.db.models.fields.files.FileField', [], {'max_length': '100'}),
            'mimetype': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '50', 'blank': 'True'})
        },
        'logger.instance': {
            'Meta': {'object_name': 'Instance'},
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'date_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'deleted_at': ('django.db.models.fields.DateTimeField', [], {'default': 'None', 'null': 'True'}),
            'geom': ('django.contrib.gis.db.models.fields.GeometryCollectionField', [], {'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'json': ('jsonfield.fields.JSONField', [], {'default': '{}'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "u'submitted_via_web'", 'max_length': '20'}),
            'survey_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['logger.SurveyType']"}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'instances'", 'null': 'True', 'to': u"orm['auth.User']"}),
            'uuid': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '249'}),
            'xform': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'instances'", 'null': 'True', 'to': "orm['logger.XForm']"}),
            'xml': ('django.db.models.fields.TextField', [], {})
        },
        'logger.instancehistory': {
            'Meta': {'object_name': 'InstanceHistory'},
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'date_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'uuid': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '249'}),
            'xform_instance': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'submission_history'", 'to': "orm['logger.Instance']"}),
            'xml': ('django.db.models.fields.TextField', [], {})
        },
        'logger.note': {
            'Meta': {'object_name': 'Note'},
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'date_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instance': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'notes'", 'to': "orm['logger.Instance']"}),
            'note': ('django.db.models.fields.TextField', [], {})
        },
        'logger.project': {
            'Meta': {'unique_together': "(('name', 'organization'),)", 'object_name': 'Project'},
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'project_creator'", 'to': u"orm['auth.User']"}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'date_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'metadata': ('jsonfield.fields.JSONField', [], {'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'organization': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'project_organization'", 'to': u"orm['auth.User']"}),
            'shared': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'user_stars': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.User']", 'symmetrical': 'False'})
        },
        'logger.surveytype': {
            'Meta': {'object_name': 'SurveyType'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'slug': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'})
        },
        'logger.xform': {
            'Meta': {'ordering': "('id_string',)", 'unique_together': "(('user', 'id_string', 'project'), ('user', 'sms_id_string', 'project'))", 'object_name': 'XForm'},
            'allows_sms': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'bamboo_dataset': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '60'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'date_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'default': "u''", 'null': 'True'}),
            'downloadable': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'encrypted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'has_start_time': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'id_string': ('django.db.models.fields.SlugField', [], {'max_length': '100'}),
            'instances_with_geopoints': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'json': ('django.db.models.fields.TextField', [], {'default': "u''"}),
            'last_submission_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'num_of_submissions': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'project': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['logger.Project']"}),
            'require_auth': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'shared': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'shared_data': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'sms_id_string': ('django.db.models.fields.SlugField', [], {'default': "''", 'max_length': '100'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'xforms'", 'null': 'True', 'to': u"orm['auth.User']"}),
            'uuid': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '32'}),
            'xls': ('django.db.models.fields.files.FileField', [], {'max_length': '100', 'null': 'True'}),
            'xml': ('django.db.models.fields.TextField', [], {})
        },
        'logger.ziggyinstance': {
            'Meta': {'object_name': 'ZiggyInstance'},
            'client_version': ('django.db.models.fields.BigIntegerField', [], {'default': 'None', 'null': 'True'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'date_deleted': ('django.db.models.fields.DateTimeField', [], {'default': 'None', 'null': 'True'}),
            'date_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'entity_id': ('django.db.models.fields.CharField', [], {'max_length': '249'}),
            'form_instance': ('django.db.models.fields.TextField', [], {}),
            'form_version': ('django.db.models.fields.CharField', [], {'default': "u'1.0'", 'max_length': '10'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instance_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '249'}),
            'reporter': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'ziggys'", 'to': u"orm['auth.User']"}),
            'server_version': ('django.db.models.fields.BigIntegerField', [], {}),
            'xform': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'ziggy_submissions'", 'null': 'True', 'to': "orm['logger.XForm']"})
        }
    }

    complete_apps = ['logger']