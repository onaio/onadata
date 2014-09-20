import json

from django.contrib.auth.decorators import login_required
from django.db.utils import IntegrityError
from django.http import HttpResponse
from django.shortcuts import render
from django.shortcuts import get_object_or_404
from django.template.base import Template
from django.template.context import Context
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _

from onadata.apps.logger.models.xform import XForm
from onadata.apps.restservice.forms import RestServiceForm
from onadata.apps.restservice.models import RestService


@login_required
def add_service(request, username, id_string):
    data = {}
    form = RestServiceForm()
    xform = get_object_or_404(
        XForm, user__username__iexact=username, id_string__iexact=id_string)
    if request.method == 'POST':
        form = RestServiceForm(request.POST)
        restservice = None
        if form.is_valid():
            service_name = form.cleaned_data['service_name']
            service_url = form.cleaned_data['service_url']
            try:
                rs = RestService(service_url=service_url,
                                 name=service_name, xform=xform)
                rs.save()
            except IntegrityError:
                message = _(u"Service already defined.")
                status = 'fail'
            else:
                status = 'success'
                message = (_(u"Successfully added service %(name)s.")
                           % {'name': service_name})
                service_tpl = render_to_string("service.html", {
                    "sv": rs, "username": xform.user.username,
                    "id_string": xform.id_string})
                restservice = service_tpl
        else:
            status = 'fail'
            message = _(u"Please fill in all required fields")

            if form.errors:
                for field in form:
                    message += Template(u"{{ field.errors }}")\
                        .render(Context({'field': field}))
        if request.is_ajax():
            response = {'status': status, 'message': message}
            if restservice:
                response["restservice"] = u"%s" % restservice

            return HttpResponse(json.dumps(response))

        data['status'] = status
        data['message'] = message

    data['list_services'] = RestService.objects.filter(xform=xform)
    data['form'] = form
    data['username'] = username
    data['id_string'] = id_string

    return render(request, "add-service.html", data)


def delete_service(request, username, id_string):
    success = "FAILED"
    if request.method == 'POST':
        pk = request.POST.get('service-id')
        if pk:
            try:
                rs = RestService.objects.get(pk=int(pk))
            except RestService.DoesNotExist:
                pass
            else:
                rs.delete()
                success = "OK"

    return HttpResponse(success)
