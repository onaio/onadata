from registration.backends.default.views import RegistrationView

from onadata.apps.main.models import UserProfile


class FHRegistrationView(RegistrationView):
    def register(self, request, **cleaned_data):
        new_user = \
            super(FHRegistrationView, self).register(request, **cleaned_data)
        new_profile = \
            UserProfile(user=new_user, name=cleaned_data['name'],
                        city=cleaned_data['city'],
                        country=cleaned_data['country'],
                        organization=cleaned_data['organization'],
                        home_page=cleaned_data['home_page'],
                        twitter=cleaned_data['twitter'])
        new_profile.save()
        return new_user
