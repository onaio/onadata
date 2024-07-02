# -*- coding: utf-8 -*-
"""
Implements the AuthenticateHeaderMixin class

Set's the appropriate authentication header using either the TempToken or Token.
"""
from rest_framework.authentication import TokenAuthentication, get_authorization_header

from onadata.libs.authentication import TempTokenAuthentication


class AuthenticateHeaderMixin:  # pylint: disable=too-few-public-methods
    """
    Implements the AuthenticateHeaderMixin class

    Set's the appropriate authentication header using either the TempToken or Token.
    """

    def get_authenticate_header(self, request):
        """
        Set's the appropriate authentication header using either the TempToken or Token.
        """
        auth = get_authorization_header(request).split()

        if auth and auth[0].lower() == b"token":
            return TokenAuthentication().authenticate_header(request)

        if auth and auth[0].lower() == b"temptoken":
            return TempTokenAuthentication().authenticate_header(request)

        return super().get_authenticate_header(request)
