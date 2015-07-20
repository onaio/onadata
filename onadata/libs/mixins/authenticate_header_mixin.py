from rest_framework.authentication import get_authorization_header
from rest_framework.authentication import TokenAuthentication
from onadata.libs.authentication import TempTokenAuthentication


class AuthenticateHeaderMixin(object):
    def get_authenticate_header(self, request):
        auth = get_authorization_header(request).split()

        if auth and auth[0].lower() == b'token':
            return TokenAuthentication().authenticate_header(request)

        if auth and auth[0].lower() == b'temptoken':
            return TempTokenAuthentication().authenticate_header(request)

        return super(AuthenticateHeaderMixin, self)\
            .get_authenticate_header(request)
