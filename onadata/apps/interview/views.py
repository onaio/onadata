import requests
from requests.auth import HTTPBasicAuth
from django.http import JsonResponse
from rest_framework.generics import ListAPIView
from onadata.apps.logger.models import XForm
import xmltodict
from django.shortcuts import get_object_or_404
from rest_framework import status
import os
from rest_framework.authentication import TokenAuthentication, BasicAuthentication
from rest_framework.response import Response
from django.shortcuts import render
import json


# Go to http://localhost:8000/api/v1/form/<form_id>/
class FetchOnadataFormView(ListAPIView):
    lookup_field = "pk"
    authentication_classes = [BasicAuthentication, TokenAuthentication]

    def get(self, request, *args, **kwargs):
        try:
            # Define authentication of admin user credentials
            username = "kenlao"  # Replace with environmental variables in production, I used this for simplicity
            password = "admin123"

            # Define the endpoint URL
            pk = kwargs.get("pk")
            model = get_object_or_404(XForm, id=pk)
            if model:
                print("YES!!")
                endpoint = f"http://localhost:8000/api/v1/formlist/{pk}"

                # Send a GET request to the endpoint with basic authentication
                response = requests.get(
                    endpoint, auth=HTTPBasicAuth(username, password)
                )

                # Check for HTTP errors
                response.raise_for_status()

                # Access the XML response as text
                xml_data = response.text

                # Parse the XML into a Python dictionary using xmltodict
                data_dict = xmltodict.parse(xml_data)
                h_head = data_dict.get("h:html", {}).get("h:head", {})

                # Return the parsed h_head as JSON response
                # return JsonResponse(h_head, safe=False)
                return render(
                    request, "display_data.html", {"data": json.dumps(h_head)}
                )

        except requests.exceptions.HTTPError as http_err:
            return Response(
                {"error": f"HTTP error occurred: {str(http_err)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except requests.exceptions.RequestException as req_err:
            return Response(
                {"error": f"Request error: {str(req_err)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            return Response(
                {"error": f"An unexpected error occurred: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
