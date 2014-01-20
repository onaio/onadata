from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404

from onadata.apps.odk_logger.models import XForm
from onadata.apps.stats.utils import get_form_submissions_per_day


@login_required
def stats(request, username=None, id_string=None):
    context = RequestContext(request)
    if id_string:
        xform = get_object_or_404(
            XForm, user=request.user, id_string=id_string)
        context.xform = xform
        context.submission_stats = get_form_submissions_per_day(xform)
    else:
        context.xforms = XForm.objects.filter(user=request.user)
    return render_to_response('form-stats.html', context_instance=context)


@staff_member_required
def submissions(request):
    context = RequestContext(request)

    stats = {}
    stats['submission_count'] = {}
    stats['submission_count']['total_submission_count'] = 0

    users = User.objects.all()
    for user in users:
        stats['submission_count'][user.username] = 0
        stats['submission_count'][user.username] += user.instances.count()
        stats['submission_count'][
            'total_submission_count'] += user.instances.count()
    context.stats = stats
    return render_to_response("submissions.html", context_instance=context)
