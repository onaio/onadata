from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.shortcuts import render

from onadata.apps.logger.models import XForm
from onadata.apps.stats.utils import get_form_submissions_per_day


@login_required
def stats(request, username=None, id_string=None):
    if id_string:
        xform = get_object_or_404(
            XForm, user=request.user, id_string__iexact=id_string)
        data = {
            'xform': xform,
            'context.submission_stats': get_form_submissions_per_day(xform)
        }
    else:
        data = {'xforms': XForm.objects.filter(user=request.user)}
    return render(request, 'form-stats.html', data)


@staff_member_required
def submissions(request):
    stats = {}
    stats['submission_count'] = {}
    stats['submission_count']['total_submission_count'] = 0

    users = User.objects.all()
    for user in users:
        stats['submission_count'][user.username] = 0
        stats['submission_count'][user.username] += user.instances.count()
        stats['submission_count'][
            'total_submission_count'] += user.instances.count()

    return render(request, "submissions.html", {'stats': stats})
