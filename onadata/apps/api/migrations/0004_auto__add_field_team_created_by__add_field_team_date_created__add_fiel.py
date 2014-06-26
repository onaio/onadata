# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'Team.created_by'
        db.add_column(u'api_team', 'created_by',
                      self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='team_creator', null=True, to=orm['auth.User']),
                      keep_default=False)

        # Adding field 'Team.date_created'
        db.add_column(u'api_team', 'date_created',
                      self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, null=True, blank=True),
                      keep_default=False)

        # Adding field 'Team.date_modified'
        db.add_column(u'api_team', 'date_modified',
                      self.gf('django.db.models.fields.DateTimeField')(auto_now=True, null=True, blank=True),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'Team.created_by'
        db.delete_column(u'api_team', 'created_by_id')

        # Deleting field 'Team.date_created'
        db.delete_column(u'api_team', 'date_created')

        # Deleting field 'Team.date_modified'
        db.delete_column(u'api_team', 'date_modified')


    models = {
        'api.organizationprofile': {
            'Meta': {'object_name': 'OrganizationProfile', '_ormbases': ['main.UserProfile']},
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']"}),
            'is_organization': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            u'userprofile_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['main.UserProfile']", 'unique': 'True', 'primary_key': 'True'})
        },
        'api.project': {
            'Meta': {'unique_together': "(('name', 'organization'),)", 'object_name': 'Project'},
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'project_creator'", 'to': u"orm['auth.User']"}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'date_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'organization': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'project_organization'", 'to': u"orm['auth.User']"})
        },
        'api.projectxform': {
            'Meta': {'unique_together': "(('xform', 'project'),)", 'object_name': 'ProjectXForm'},
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'project': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['api.Project']"}),
            'xform': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['logger.XForm']"})
        },
        'api.team': {
            'Meta': {'object_name': 'Team', '_ormbases': [u'auth.Group']},
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'team_creator'", 'null': 'True', 'to': u"orm['auth.User']"}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'null': 'True', 'blank': 'True'}),
            'date_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'null': 'True', 'blank': 'True'}),
            u'group_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['auth.Group']", 'unique': 'True', 'primary_key': 'True'}),
            'organization': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']"}),
            'projects': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['api.Project']", 'symmetrical': 'False'})
        },
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
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'logger.xform': {
            'Meta': {'ordering': "('id_string',)", 'unique_together': "(('user', 'id_string'), ('user', 'sms_id_string'))", 'object_name': 'XForm'},
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
            'num_of_submissions': ('django.db.models.fields.IntegerField', [], {'default': '-1'}),
            'shared': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'shared_data': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'sms_id_string': ('django.db.models.fields.SlugField', [], {'default': "''", 'max_length': '100'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'xforms'", 'null': 'True', 'to': u"orm['auth.User']"}),
            'uuid': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '32'}),
            'xls': ('django.db.models.fields.files.FileField', [], {'max_length': '100', 'null': 'True'}),
            'xml': ('django.db.models.fields.TextField', [], {})
        },
        'main.userprofile': {
            'Meta': {'object_name': 'UserProfile'},
            'address': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'city': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'country': ('django.db.models.fields.CharField', [], {'max_length': '2', 'blank': 'True'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']", 'null': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'home_page': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'num_of_submissions': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'organization': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'phonenumber': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'require_auth': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'twitter': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'profile'", 'unique': 'True', 'to': u"orm['auth.User']"})
        },
        u'taggit.tag': {
            'Meta': {'object_name': 'Tag'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'}),
            'slug': ('django.db.models.fields.SlugField', [], {'unique': 'True', 'max_length': '100'})
        },
        u'taggit.taggeditem': {
            'Meta': {'object_name': 'TaggedItem'},
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "u'taggit_taggeditem_tagged_items'", 'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'object_id': ('django.db.models.fields.IntegerField', [], {'db_index': 'True'}),
            'tag': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "u'taggit_taggeditem_items'", 'to': u"orm['taggit.Tag']"})
        }
    }

    complete_apps = ['api']