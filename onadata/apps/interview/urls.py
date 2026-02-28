from django.urls import path
from . import views


urlpatterns = [
    path(
        "form/<int:pk>/",
        views.FetchOnadataFormView.as_view(),
        name="form_id",
    ),
]
