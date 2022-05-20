# -*- coding: utf-8 -*-
"""
Base class.
"""


class RestServiceInterface:
    """RestServiceInterface base class."""

    def send(self, url, data=None):
        """The class method to implement when sending data."""
        raise NotImplementedError
