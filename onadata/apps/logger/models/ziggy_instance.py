import json
import time
from django.db import models
from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from jsonfield import JSONField

from onadata.apps.logger.models import XForm
from onadata.apps.restservice.utils import call_ziggy_services
from onadata.libs.utils import common_tags


def save_entity(instance, zi, new_form_instance, reporter, ziggy_entity=None):
    data = {
        '_id': zi.entity_id,
        'instanceId': zi.instance_id,
        'entityId': zi.entity_id,
        'formInstance': new_form_instance,
        'formName': instance.get('formName'),
        'clientVersion': zi.client_version,
        'serverVersion': zi.server_version,
        'formDataDefinitionVersion': zi.form_version,
        'reporterId': reporter.username
    }
    if ziggy_entity:
        ziggy_entity.data = data
    else:
        ziggy_entity = ZiggyEntity(data=data, entity_id=zi.entity_id)

    ziggy_entity.save()


class ZiggyEntity(models.Model):
    data = JSONField()
    entity_id = models.CharField(max_length=249, null=False)

    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    date_deleted = models.DateTimeField(null=True, default=None)

    class Meta:
        app_label = 'logger'


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
    form_instance = JSONField()
    reporter = models.ForeignKey(User, related_name='ziggys', null=False)
    client_version = models.BigIntegerField(null=True, default=None)
    server_version = models.BigIntegerField()
    form_version = models.CharField(max_length=10, default=u'1.0')
    xform = models.ForeignKey(XForm, null=True,
                              related_name='ziggy_submissions')

    # shows when we first received this instance
    date_created = models.DateTimeField(auto_now_add=True)
    # this will end up representing "date last parsed"
    date_modified = models.DateTimeField(auto_now=True)
    # this will end up representing "date instance was deleted"
    date_deleted = models.DateTimeField(null=True, default=None)

    class Meta:
        app_label = 'logger'

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
    def create_ziggy_instance(cls, user, instance, reporter):
        entity_id = instance['entityId']
        instance_id = instance['instanceId']
        form_instance = json.loads(instance['formInstance'])
        client_version = instance['clientVersion']
        form_version = instance['formDataDefinitionVersion']
        form_name = instance['formName']

        try:
            xform = XForm.objects.get(user=user, id_string=form_name)
        except XForm.DoesNotExist:
            xform = None

        zi = ZiggyInstance(
            entity_id=entity_id, instance_id=instance_id,
            reporter=reporter, client_version=client_version,
            form_instance=form_instance, form_version=form_version,
            xform=xform)
        return zi

    @classmethod
    def create_ziggy_instances(cls, form_user, json_post):
        instances = json.loads(json_post)
        data = []
        reporter = None
        for instance in sorted(instances, key=lambda k: k['clientVersion']):
            reporter_id = instance['reporterId']
            if reporter is None:
                reporter = get_object_or_404(User, username=reporter_id)

            zi = cls.create_ziggy_instance(form_user, instance, reporter)
            zi.save()
            data.append(zi.pk)

            # get ths formInstance within the db if it exists
            entities = ZiggyEntity.objects.filter(entity_id=zi.entity_id)
            ziggy_entity = None

            if entities.count():
                entity = entities[0].data
                existing_form_instance = entity['formInstance']
                existing_field_data = existing_form_instance['form']['fields']
                new_field_data = zi.form_instance['form']['fields']
                existing_field_data = ZiggyInstance.merge_ziggy_form_instances(
                    existing_field_data, new_field_data)
                existing_form_instance['form']['fields'] = existing_field_data
                new_form_instance = existing_form_instance
                ziggy_entity = entities[0]
            else:
                new_form_instance = zi.form_instance

            save_entity(instance, zi, new_form_instance, reporter,
                        ziggy_entity)

        return len(data)

    @classmethod
    def get_current_list(cls, reporter_id, client_version):
        """Returns ziggy entities for specified reporter and client_version
        greater or equal integer valuei.

        :param string reporter_id: reporter's username
        :client_version integer client_version:
            or string of the ziggy client version.

        :raises TypeError: if not an integer

        :return: with the json entities
        :rtype: ZiggyEntity ValuesQueryset
        """
        client_version = int(client_version)
        # need to ensure params are in a string for json query
        # not to raise a explicity type cast error
        return ZiggyEntity.objects.values_list('data', flat=True).extra(
            where=['data->>%s = %s', 'data->>%s >= %s'],
            params=['reporterId', unicode(reporter_id),
                    'clientVersion', unicode(client_version)])

    @classmethod
    def field_by_name_exists(cls, name):
        """ Returns a function that can be used with the filter method

        @param name: the name key to look for
        @return: a function to use with filter
        """
        def _equal(rec):
            return rec['name'] == name

        return _equal

    @classmethod
    def merge_ziggy_form_instances(cls, source_data, update_data):
        for item in update_data:
            # check for the item in a, update if it exists otherwise append
            matches = filter(
                cls.field_by_name_exists(item['name']), source_data)
            if len(matches) > 0:
                match = matches[0]
                match.update(item)
            else:
                source_data.append(item)
        return source_data


def ziggy_to_formhub_instance(ziggy_instance):
    # todo: use form's fields to map fields to values
    ziggy_dict = ziggy_instance.form_instance.copy()
    formhub_dict = {}
    for field in ziggy_dict['form']['fields']:
        if 'bind' in field:
            field_name = field['bind'].split('/')[-1]
            formhub_dict[field_name] = field.get('value', '')
    formhub_dict[common_tags.USERFORM_ID] = '{}_{}'.format(
        ziggy_instance.xform.user.username, ziggy_instance.xform.id_string)
    return formhub_dict


def rest_service_ziggy_submission(sender, instance, raw, created,
                                  update_fields, **kwargs):
    # TODO: this only works if the formName within ziggy matches this form's
    # name
    if created and instance.xform:
        services_called = call_ziggy_services(instance, instance.pk)

        return services_called

post_save.connect(rest_service_ziggy_submission, sender=ZiggyInstance)
