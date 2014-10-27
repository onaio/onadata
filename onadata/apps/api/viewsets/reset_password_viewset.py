from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail

from onadata.settings.common import DEFAULT_FROM_EMAIL

from rest_framework import status
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet


class ResetPasswordViewSet(ViewSet):

    """

## Request password reset
<pre class="prettyprint">
<b>POST</b> /api/v1/reset
</pre>

- Sends an email to the user's email with a url that \
redirects to a reset password form on the API consumer's website.
- `email` and `reset_url` are expected in the POST payload.
- Expected url format is `reset_url=https://{{full_domain_name}}/\
{{reset_password_form_path}}`.
- Example of url that is sent to user's email is\
`http://mydomain.com/reset_form/?token=2f3f334g3r3434`.

>
> Example
>
>       curl -X POST -d email=demouser@mail.com\
 url=http://example-url.com/reset https://ona.io/api/v1/reset
>
> Response:
>
>        HTTP 200 OK


>
## Reset user password

- Resets user's password
- `email`, `token` and `new_password` are expected in the POST payload.

>
> Example
>
>       curl -X POST -d email=demouser@mail.com -d token=qndoi209jf02n4 \
-d new_password=usernewpass https://ona.io/api/v1/reset
>
> Response:
>
>        HTTP 200 OK
"""

    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):

        email = request.DATA.get('email')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        reset_url = request.DATA.get('reset_url')

        if user and reset_url:
            reset_token = default_token_generator.make_token(user)
            reset_url = reset_url + "?token=" + reset_token
            email_msg = "Click on the provided link to reset your Ona password\n " + reset_url
            send_mail("Ona Password Reset",
                      email_msg,
                      DEFAULT_FROM_EMAIL,
                      (user.email, ))
            return Response(status=status.HTTP_200_OK)

        token = request.DATA.get('token')
        new_password = request.DATA.get('new_password')

        if user and token and new_password:
            if default_token_generator.check_token(user, token):
                user.set_password(new_password)
                user.save()

                return Response(status=status.HTTP_200_OK)

        return Response(status=status.HTTP_400_BAD_REQUEST)
