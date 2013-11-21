from django.contrib.auth.decorators import login_required
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404

from odk_logger.models import XForm
from .utils import get_form_submissions_per_day


@login_required
def stats(request, username=None, id_string=None):
    context = RequestContext(request)
    if id_string:
        xform = get_object_or_404(
            XForm, user=request.user, id_string=id_string)
        context.xform = xform
        context.submission_stats = get_form_submissions_per_day(xform)\
            .order_by('date')
    else:
        context.xforms = XForm.objects.filter(user=request.user)
    return render_to_response('form-stats.html', context_instance=context)
