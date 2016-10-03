from registration.backends.default.views import RegistrationView


class FHRegistrationView(RegistrationView):
    def register(self, form):
        new_user = super(FHRegistrationView, self).register(form)
        form.save_user_profile(new_user)

        return new_user
