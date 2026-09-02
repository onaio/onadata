from django.urls import path
from .views import FormSubmissionsView


urlpatterns = [
    path('<str:form_id>/', FormSubmissionsView.as_view(), name='form-submissions'),
]

