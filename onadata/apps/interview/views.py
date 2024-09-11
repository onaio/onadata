import requests
from django.http import JsonResponse
from django.shortcuts import render
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenBlacklistView,
)


def fetch_onadata_form(request, form_id):
    try:
        # Define the Onadata API URL with the form_id
        url = f"https://api.ona.io/api/v1/data/{form_id}"
        response = requests.get(url)

        # Raise error if status is not OK
        response.raise_for_status()

        # Return JSON response from the API
        return JsonResponse(response.json(), safe=False)

    except requests.exceptions.RequestException as e:
        return JsonResponse({"error": str(e)}, status=400)
