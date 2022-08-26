# -*- coding: utf-8 -*-
"""
The UserSerializer class - Users serializer
"""
from django.contrib.auth import get_user_model
from rest_framework import serializers


User = get_user_model()


class UserSerializer(serializers.HyperlinkedModelSerializer):
    """
    The UserSerializer class - Users serializer
    """

    class Meta:
        model = User
        fields = ("id", "username", "first_name", "last_name")
