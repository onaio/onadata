from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail

from onadata.settings.common import DEFAULT_FROM_EMAIL

from rest_framework import status
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet


class ResetPasswordViewSet(ViewSet):

    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):

        email = request.DATA.get('email')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        url = request.DATA.get('reset_url')

        if user and url:
            reset_token = default_token_generator.make_token(user)
            reset_url = url + "?token=" + reset_token
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
