# -*- coding: utf-8 -*-
"""
BulkCreateMixin module
"""
from __future__ import unicode_literals


class BulkCreateMixin(object):
    """
    Bulk Create Mixin
    Allows the bulk creation of resources
    """

    def get_serializer(self, *args, **kwargs):
        """
        Gets the appropriate serializer depending on if you are creating a
        single resource or many resources
        """
        if isinstance(kwargs.get('data', {}), list):
            kwargs['many'] = True

        return super(BulkCreateMixin, self).get_serializer(*args, **kwargs)
