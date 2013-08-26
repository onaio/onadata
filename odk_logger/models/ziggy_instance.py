import json
import time
from django.db import models
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.conf import settings


mongo_ziggys = settings.MONGO_DB.ziggys


class ZiggyInstance(models.Model):
    """
        - ZiggyInstance Django Model
            - id_string/form_id - which form?
                - normal form?
                - special form that links several forms or entities
            - entity_id
            - instance_id
            - reporter_id
            - form_instance - actual json string
                - should we store separetely
            - client_version
            - server_version
            - form_data_version?
    """
    entity_id = models.CharField(max_length=249, null=False)
    instance_id = models.CharField(max_length=249, null=False, unique=True)
    form_instance = models.TextField()
    reporter = models.ForeignKey(User, related_name='ziggys', null=False)
    client_version = models.BigIntegerField(null=True, default=None)
    server_version = models.BigIntegerField()
    form_version = models.CharField(max_length=10, default=u'1.0')

    # shows when we first received this instance
    date_created = models.DateTimeField(auto_now_add=True)
    # this will end up representing "date last parsed"
    date_modified = models.DateTimeField(auto_now=True)
    # this will end up representing "date instance was deleted"
    date_deleted = models.DateTimeField(null=True, default=None)

    class Meta:
        app_label = 'odk_logger'

    def save(self, *args, **kwargs):
        self.server_version = int(time.time() * 1000)
        super(ZiggyInstance, self).save(*args, **kwargs)

    def to_ziggy_dict(self):
        obj = {
            'entityId': self.entity_id,
            'formName': '',
            'instanceId': self.instance_id,
            'formInstance': self.form_instance,
            'clientVersion': self.client_version,
            'serverVersion': self.server_version,
            'formDataDefinitionVersion': self.form_version
        }
        return obj

    @classmethod
    def create_ziggy_instances(cls, json_post):
        instances = json.loads(json_post)
        data = []
        reporter = None
        for instance in sorted(instances, key=lambda k: k['clientVersion']):
            entity_id = instance['entityId']
            instance_id = instance['instanceId']
            form_instance = instance['formInstance']
            client_version = instance['clientVersion']
            reporter_id = instance['reporterId']
            form_version = instance['formDataDefinitionVersion']
            if reporter is None:
                reporter = get_object_or_404(User, username=reporter_id)
            zi = ZiggyInstance.objects.create(
                entity_id=entity_id, instance_id=instance_id,
                reporter=reporter, client_version=client_version,
                form_instance=form_instance, form_version=form_version)
            data.append(zi.pk)

            # get ths formInstance within the db if it exists
            entity = mongo_ziggys.find_one(entity_id)
            if entity:
                existing_form_instance = json.loads(entity['formInstance'])
                existing_field_data = existing_form_instance['form']['fields']
                new_field_data = json.loads(form_instance)['form']['fields']
                existing_field_data = ZiggyInstance.merge_ziggy_form_instances(
                    existing_field_data, new_field_data)
                existing_form_instance['form']['fields'] = existing_field_data
                form_instance = json.dumps(existing_form_instance)

            mongo_data = {
                '_id': entity_id,
                'instanceId': instance_id,
                'entityId': entity_id,
                'formInstance': form_instance,
                'formName': instance.get('formName'),
                'clientVersion': client_version,
                'serverVersion': zi.server_version,
                'formDataDefinitionVersion': form_version,
                'reporterId': reporter.username
            }
            mongo_ziggys.save(mongo_data)
        return len(data)

    @classmethod
    def get_current_list(cls, reporter_id, client_version):
        query = {
            'reporterId': reporter_id,
            'serverVersion': {'$gte': int(client_version)}
        }
        return mongo_ziggys.find(query)

    @classmethod
    def field_by_name_exists(cls, name):
        """ Returns a function that can be used with the filter method

        @param name: the name key to look for
        @return: a function to use with filter
        """
        return lambda rec: rec['name'] == name

    @classmethod
    def merge_ziggy_form_instances(cls, source_data, update_data):
        for item in update_data:
            # check for the item in a, update if it exists otherwise append to a
            matches = filter(
                cls.field_by_name_exists(item['name']), source_data)
            if len(matches) > 0:
                match = matches[0]
                match.update(item)
            else:
                source_data.append(item)
        return source_data
