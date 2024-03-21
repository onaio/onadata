# -*- coding: utf-8 -*-
"""
restservice views.
"""

from django.contrib.auth.decorators import login_required
from django.db.utils import IntegrityError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.base import Template
from django.template.context import Context
from django.template.loader import render_to_string
from django.utils.translation import gettext as _

from onadata.apps.restservice.forms import RestServiceForm
from onadata.apps.restservice.models import RestService
from onadata.libs.utils.viewer_tools import get_form


@login_required
def add_service(request, username, id_string):
    """Add a service."""
    data = {}
    form = RestServiceForm()

    xform = get_form(
        {"id_string__iexact": id_string, "user__username__iexact": username}
    )
    if request.method == "POST":
        form = RestServiceForm(request.POST)
        restservice = None
        if form.is_valid():
            service_name = form.cleaned_data["service_name"]
            service_url = form.cleaned_data["service_url"]
            try:
                service = RestService(
                    service_url=service_url, name=service_name, xform=xform
                )
                service.save()
            except IntegrityError:
                message = _("Service already defined.")
                status = "fail"
            else:
                status = "success"
                message = _("Successfully added service %(name)s.") % {
                    "name": service_name
                }
                service_tpl = render_to_string(
                    "service.html",
                    {
                        "sv": service,
                        "username": xform.user.username,
                        "id_string": xform.id_string,
                    },
                )
                restservice = service_tpl
        else:
            status = "fail"
            message = _("Please fill in all required fields")

            if form.errors:
                for field in form:
                    message += Template("{{ field.errors }}").render(
                        Context({"field": field})
                    )
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            response = {"status": status, "message": message}
            if restservice:
                response["restservice"] = f"{restservice}"

            return JsonResponse(response)

        data["status"] = status
        data["message"] = message

    data["list_services"] = RestService.objects.filter(xform=xform)
    data["form"] = form
    data["username"] = username
    data["id_string"] = id_string

    return render(request, "add-service.html", data)


@login_required
def delete_service(request, username, id_string):
    """Delete a service view."""
    success = "FAILED"
    xform = get_form(
        {"id_string__iexact": id_string, "user__username__iexact": username}
    )
    if request.method == "POST":
        service_id = request.POST.get("service-id")
        if service_id:
            try:
                service = RestService.objects.get(pk=int(service_id), xform=xform)
            except RestService.DoesNotExist:
                pass
            else:
                service.delete()
                success = "OK"

    return HttpResponse(success)
