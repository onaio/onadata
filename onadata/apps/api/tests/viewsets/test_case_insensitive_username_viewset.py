from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import connection
from rest_framework.test import APIRequestFactory, force_authenticate
from onadata.apps.api.viewsets.user_profile_viewset import UserProfileViewSet
from onadata.apps.main.models import UserProfile


# imports the model which we are testing which is user
User = get_user_model()

class TestCaseInsensitiveUserQuery(TestCase):


    ''' 
        Method runs sql to create citext within test database if the 
        citext migration fails.
    '''
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Ensures that citext extension exists
        with connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS citext;")
        
            cursor.execute("""
                ALTER TABLE auth_user 
                ALTER COLUMN username TYPE citext;
            """)


    '''
        Method creates test user 'Bob' along with a useprofile. This is done to 
        simulate the api returning a valid user object.
    '''
    def setUp(self):
        self.factory = APIRequestFactory()

        # Create test user 'Bob'
        self.user1 = User.objects.create_user(username="Bob", password="pass123")
        
        # Create a superuser for authentication
        self.admin = User.objects.create_superuser(username="admin", password="adminpass")
        
        # Create UserProfiles for each user which is required by the viewset
        UserProfile.objects.create(user=self.user1)
        UserProfile.objects.create(user=self.admin)

        # Set up the view
        self.view = UserProfileViewSet.as_view({"get": "list"})


    '''
        Method tests different case versions of the username in order to test 
        citext case insensitivity.
    '''
    def test_single_username_case_insensitive(self):


        # makes call to api endpoint and returns object stored in request
        request = self.factory.get("/api/v1/profiles.json", {"users": "Bob"})

        # line simulates request being run by admin user, bypassing authentication
        force_authenticate(request, user=self.admin)
        response = self.view(request)

        # assets check whether response was valid and if it returned any data at all. 
        self.assertEqual(response.status_code, 200)

        # most important assert. If fails, it implies a failure in case insensitivity
        self.assertEqual(len(response.data), 1)


        request = self.factory.get("/api/v1/profiles.json", {"users": "bob"})
        force_authenticate(request, user=self.admin)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)


        request = self.factory.get("/api/v1/profiles.json", {"users": "bOb"})
        force_authenticate(request, user=self.admin)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

