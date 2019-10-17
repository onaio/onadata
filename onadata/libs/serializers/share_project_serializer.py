from django.contrib.auth.models import User
from django.utils.translation import ugettext as _

from rest_framework import serializers
from onadata.libs.models.share_project import ShareProject
from onadata.libs.permissions import get_object_users_with_permissions
from onadata.libs.permissions import ROLES
from onadata.libs.permissions import OwnerRole
from onadata.libs.serializers.fields.project_field import ProjectField


def attrs_to_instance(attrs, instance):
    instance.project = attrs.get('project', instance.project)
    instance.username = attrs.get('username', instance.username)
    instance.role = attrs.get('role', instance.role)
    instance.remove = attrs.get('remove', instance.remove)

    return instance


class ShareProjectSerializer(serializers.Serializer):
    project = ProjectField()
    username = serializers.CharField(max_length=255,
                                     allow_null=True,
                                     required=False)
    usernames = serializers.CharField(required=False)
    role = serializers.CharField(max_length=50)

    def create(self, validated_data):
        if "usernames" in validated_data:
            usernames = validated_data.pop('usernames')
            created_instances = []

            for username in usernames:
                validated_data['username'] = username
                instance = ShareProject(**validated_data)
                instance.save()
                created_instances.append(instance)

            return created_instances
        else:
            instance = ShareProject(**validated_data)
            instance.save()
            return instance

    def update(self, instance, validated_data):
        instance = attrs_to_instance(validated_data, instance)
        instance.save()

        return instance

    def validate(self, attrs):
        # Check that either the 'username' or 'usernames' field is passed
        if not attrs.get('username') and not attrs.get('usernames'):
            raise serializers.ValidationError({
                'username':
                _(u"Either username or usernames field should be present"),
                'usernames':
                _(u"Either username or usernames field should be present")
            })

        if attrs.get('usernames'):
            usernames = attrs.get('usernames')
        else:
            usernames = [attrs.get('username')]

        for username in usernames:
            user = User.objects.get(username=username)
            project = attrs.get('project')

            # check if the user is the owner of the project
            if user and project:
                if user == project.organization:
                    raise serializers.ValidationError({
                        'username':
                        _(u"Cannot share project with the owner (%(value)s)" %
                          {"value": user.username})
                    })

        return attrs

    def validate_username(self, value):
        """Check that the username exists"""

        user = None
        try:
            user = User.objects.get(username=value)
        except User.DoesNotExist:
            raise serializers.ValidationError(_(
                u"User '%(value)s' does not exist." % {"value": value}
            ))
        else:
            if not user.is_active:
                raise serializers.ValidationError(_(u"User is not active"))

        return value

    def validate_usernames(self, value):
        """Check that all usernames in the list exist"""
        usernames = value.split(',')

        for username in usernames:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                raise serializers.ValidationError(
                    _(u"User '%(username)s' does not exist." %
                      {"username": username}))
            else:
                if not user.is_active:
                    raise serializers.ValidationError(
                        _(u"User '%(username)s' is not active") %
                        {"username": username})

        return usernames

    def validate_role(self, value):
        """check that the role exists"""
        if value not in ROLES:
            raise serializers.ValidationError(_(
                u"Unknown role '%(role)s'." % {"role": value}
            ))

        return value


class RemoveUserFromProjectSerializer(ShareProjectSerializer):
    remove = serializers.BooleanField()

    def update(self, instance, validated_data):
        instance = attrs_to_instance(validated_data, instance)
        instance.save()

        return instance

    def create(self, validated_data):
        instance = ShareProject(**validated_data)
        instance.save()

        return instance

    def validate(self, attrs):
        """ Check and confirm that the project will be left with at least one
         owner. Raises a validation error if only one owner found"""

        if attrs.get('role') == OwnerRole.name:
            results = get_object_users_with_permissions(attrs.get('project'))

            # count all the owners
            count = len(
                [res for res in results if res.get('role') == OwnerRole.name]
            )

            if count <= 1:
                raise serializers.ValidationError({
                    'remove': _(u"Project requires at least one owner")
                })

        return attrs
