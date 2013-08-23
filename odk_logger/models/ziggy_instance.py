import json
import time
from django.db import models
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404


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
            'serverVersion': self.server_version
        }
        return obj

    @classmethod
    def create_ziggy_instances(cls, json_post):
        instances = json.loads(json_post)
        data = []
        reporter = None
        for instance in sorted(instances, key=lambda k: k['clientVersion']):
            assert 'entityId' in instance
            entity_id = instance['entityId']
            assert 'instanceId' in instance
            instance_id = instance['instanceId']
            assert 'formInstance' in instance
            form_instance = instance['formInstance']
            # assert 'server_version' in instance
            # server_version = instance['server_version']
            assert 'clientVersion' in instance
            client_version = instance['clientVersion']
            assert 'reporterId' in instance
            reporter_id = instance['reporterId']
            if reporter is None:
                reporter = get_object_or_404(User, username=reporter_id)
            zi = ZiggyInstance.objects.create(
                entity_id=entity_id, instance_id=instance_id,
                reporter=reporter, client_version=client_version,
                form_instance=form_instance)
            data.append(zi)
        return len(data)

    @classmethod
    def get_current_list(cls, reporter_id, client_version):
        data = []
        instances = ZiggyInstance.objects.filter(
            reporter__username=reporter_id, server_version__gt=client_version)
        for instance in instances:
            data.append(instance.to_ziggy_dict())
        return data
