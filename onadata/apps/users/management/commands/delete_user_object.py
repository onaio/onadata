"""Functionality to transfer a project form one owner to another."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


from onadata.apps.logger.models import Project, XForm

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
            '--object_name',
            help='',
        )

    def validate_user_owns_object(self, user, instance):
        """
        Given an instance determine if the the user provided is the one who
        created it.
        """
        is_valid_owner = False
        if obj.created_by != user:
            self.errors.append(
                'The user provided is not the owner of the object '
                ' to be deleted')
        else:
            is_valid_owner = True
        return is_valid_owner

    def get_instance(self, object_type, obj_name):
        """"
        Given an instance type and name, return the instance if it exists and
        indicate that the instance does not exist
        """
        obj_class = OBJECTS_TYPE_MAP.get(object_type)
        if not obj_class:
            self.errors.append(
                '{} is not a valid object_type'.format(object_type))
            return
        try:
            return obj_class.objects.get(name=obj_name)
        except obj_class.DoesNotExist:
            self.errors.append('{} does not exist'.format(obj_name))
            return

    def get_user(self, username):
        """Given a username return the user instance or indicate they do
        not exist"""
        user_model =  get_user_model()
        user = None
        try:
            user = user_model.objects.get(username=username)
        except user_model.DoesNotExist:
            self.errors = '{} does not exist'.format(username)
        return user


    def handle(self, *args, **options):  # pylint: disable=C0111
        username = options['username']
        object_type =  options.get('object_type', None)
        object_name = options.get('object_name', None)

        user = self.get_user(username)
        if user:
            self.stdout.write(self.style.ERROR(''.join(self.errors)))
            return

        instance = self.get_instance(object_type, object_name)
        if not instance:
            self.stdout.write(self.style.ERROR(''.join(self.errors)))
            return

        if not self.validate_user_owns_object(user, instance):
            self.stdout.write(self.style.ERROR(''.join(self.errors)))
            return
        instance.soft_delete()
        message = '{} with name {}  owned by {} deleted successfully.'.format(
            object_type, object_name, username
        )
        self.stdout.write(self.style.SUCCESS(message))
