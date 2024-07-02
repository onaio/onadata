# -*- coding: utf-8 -*-
"""
Base class.
"""


class RestServiceInterface:  # pylint: disable=too-few-public-methods
    """RestServiceInterface base class."""

    def send(self, url, data=None):
        """The class method to implement when sending data."""
        raise NotImplementedError
