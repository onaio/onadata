from django.conf import settings
from django.contrib.auth.models import User
from django.test import TransactionTestCase
from datetime import timedelta
from django.utils.timezone import now

from onadata.libs.serializers.user_profile_serializer import\
    UserProfileWithTokenSerializer
from onadata.apps.main.models import UserProfile
from onadata.apps.api.models.temp_token import TempToken
from onadata.libs.authentication import expired


PROFILE_DATA = {
    'username': 'bob',
    'email': 'bob@columbia.edu',
    'password1': 'bobbob',
    'password2': 'bobbob',
    'name': 'Bob',
    'city': 'Bobville',
    'country': 'US',
    'organization': 'Bob Inc.',
    'home_page': 'bob.com',
    'twitter': 'boberama'
}


def create_user_profile(profile_data):
    user, created = User.objects.get_or_create(
        username=profile_data['username'],
        first_name=profile_data['name'],
        email=profile_data['email'])
    user.set_password(profile_data['password1'])
    user.save()
    new_profile, created = UserProfile.objects.get_or_create(
        user=user, name=profile_data['name'],
        city=profile_data['city'],
        country=profile_data['country'],
        organization=profile_data['organization'],
        home_page=profile_data['home_page'],
        twitter=profile_data['twitter'],
        require_auth=False
    )

    return new_profile


class TestUserProfileSerializer(TransactionTestCase):

    def setUp(self):
        self.serializer = UserProfileWithTokenSerializer()
        self.user_profile = create_user_profile(PROFILE_DATA)

    def test_get_temp_token(self):
        temp_token_key = self.serializer.get_temp_token(self.user_profile)
        temp_token = TempToken.objects.get(key=temp_token_key)

        is_expired = expired(temp_token.created)

        self.assertFalse(is_expired)

    def test_get_temp_token_recreates_if_expired(self):
        temp_token, created = TempToken.objects.get_or_create(
            user=self.user_profile.user)

        day = timedelta(seconds=settings.DEFAULT_TEMP_TOKEN_EXPIRY_TIME)
        today = now()
        yesterday = today - day
        temp_token.created = yesterday
        temp_token.save()

        temp_token_key = self.serializer.get_temp_token(self.user_profile)
        temp_token = TempToken.objects.get(key=temp_token_key)

        is_expired = expired(temp_token.created)

        self.assertFalse(is_expired)
