# -*- coding: utf-8 -*-
"""
OrganizationProfile utility functions
"""
from onadata.libs.serializers.organization_serializer import OrganizationSerializer


def get_organization_members(organization):
    """Returns a dictionary of organizations members"""
    ret = {}
    data = OrganizationSerializer().get_users(organization)

    for user_data in data:
        username = user_data.pop("user")
        user_data.pop("gravatar")
        ret[username] = user_data

    return ret
