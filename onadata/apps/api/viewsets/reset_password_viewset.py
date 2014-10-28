from rest_framework import status
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet
from onadata.libs.serializers.password_reset_serializer import \
    PasswordResetSerializer, PasswordResetChangeSerializer


class ResetPasswordViewSet(ViewSet):

    """

## Request password reset
<pre class="prettyprint">
<b>POST</b> /api/v1/reset
</pre>

- Sends an email to the user's email with a url that \
redirects to a reset password form on the API consumer's website.
- `email` and `reset_url` are expected in the POST payload.
- Expected reset_url format is `reset_url=https:/domain/path/to/reset/form`.
- Example of reset url sent to user's email is\
`http://mydomain.com/reset_form?uid=Mg&token=2f3f334g3r3434`.

>
> Example
>
>       curl -X POST -d email=demouser@mail.com\
 url=http://example-url.com/reset https://ona.io/api/v1/reset
>
> Response:
>
>        HTTP 204 OK


>
## Reset user password

- Resets user's password
- `uid`, `token` and `new_password` are expected in the POST payload.
- minimum password length is 4 characters

>
> Example
>
>       curl -X POST -d uid=Mg -d token=qndoi209jf02n4 \
-d new_password=usernewpass https://ona.io/api/v1/reset
>
> Response:
>
>        HTTP 204 OK
"""

    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        context = {'request': request}
        data = request.DATA if request.DATA is not None else {}
        if 'token' in request.DATA:
            serializer = PasswordResetChangeSerializer(data=data,
                                                       context=context)
        else:
            serializer = PasswordResetSerializer(data=data, context=context)

        if serializer.is_valid():
            serializer.save()

            return Response(status=status.HTTP_204_NO_CONTENT)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
