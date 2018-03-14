
# -*- coding: utf-8 -*-
"""
Messaging notification base module.
"""
from __future__ import unicode_literals


class BaseBackend(object):  # pylint: disable=too-few-public-methods
    """
    Base class for notification backends
    """

    def send(self, instance):  # pylint: disable=unused-argument
        """
        This method actually sends the message
        """
        raise NotImplementedError()
