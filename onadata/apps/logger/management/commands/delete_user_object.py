"""Functionality to transfer a project form one owner to another."""
from itertools import chain

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


from onadata.apps.logger.models import (
    Project, XForm, DataView, MergedXForm, Instance)

OBJECTS_TYPE_MAP = {
    'xform': XForm,
    'project': Project
}


class Command(BaseCommand):  # pylint: disable=C0111
    help = ''

    errors = []

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            help='Username of the user whose objects will be deleted',
        )
        parser.add_argument(
            '--object_type',
            help='',
        )
        parser.add_argument(
            '--unique_field_value',
            help='',
        )
        parser.add_argument(
            '--unique_field',
            help='',
        )

    def validate_user_owns_object(self, user, instance):
        """
        Given an instance determine if the the user provided is the one who
        created it.
        """
        is_valid_owner = False
        if instance.created_by != user:
            self.errors.append(
                'The user provided is not the owner of the object '
                ' to be deleted')
        else:
            is_valid_owner = True
        return is_valid_owner

    def get_instance(self, object_type, unique_field, unique_field_value):
        """"
        Given an instance type and name, return the instance if it exists and
        indicate that the instance does not exist
        """
        filter_params = {
            unique_field: unique_field_value,
            'deleted_at__isnull': True
        }
        obj_class = OBJECTS_TYPE_MAP.get(object_type)
        if not obj_class:
            self.errors.append(
                '{} is not a valid object_type\n'.format(object_type))
            return
        try:
            return obj_class.objects.get(**filter_params)
        except obj_class.DoesNotExist:
            self.errors.append(
                '{} with {} {} does not exist\n'.format(
                    object_type, unique_field, unique_field_value))
            return

    def get_user(self, username):
        """
        Given a username return the user instance or indicate they do
        not exist
        """
        user_model = get_user_model()
        user = None
        try:
            user = user_model.objects.get(username=username)
        except user_model.DoesNotExist:
            self.errors.append(
                'User with username {} does not exist\n'.format(username))
        return user

    def handle(self, *args, **options):  # pylint: disable=C0111
        username = options['username']
        object_type = options.get('object_type', None)
        unique_field_value = options.get('unique_field_value', None)
        unique_field = options.get('unique_field', 'name')

        user = self.get_user(username)
        if not user:
            self.stdout.write(self.style.ERROR(''.join(self.errors)))
            return

        instance = self.get_instance(
            object_type, unique_field, unique_field_value)
        if not instance:
            self.stdout.write(self.style.ERROR(''.join(self.errors)))
            return

        if not self.validate_user_owns_object(user, instance):
            self.stdout.write(self.style.ERROR(''.join(self.errors)))
            return

        # No need to loop through the projects and delete since XForms can
        # be filtered against user
        Project.objects.filter(created_by=user).delete()

        xforms = XForm.objects.filter(user=user)
        merged_xforms = MergedXForm.objects.filter(user=user)

        for xform in chain(xforms, merged_xforms):
            DataView.objects.filter(xform=xform).delete()
            Instance.objects.filter(xform=xform).delete()

        user.delete()

        message = '{} deleted successfully.'.format(username)
        self.stdout.write(self.style.SUCCESS(message))
