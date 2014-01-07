import numpy as np

from datetime import datetime

from django.conf import settings
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.utils.translation import ugettext as _
from rest_framework import exceptions

from onadata.apps.api.models.organization_profile import OrganizationProfile
from onadata.apps.api.models.project import Project
from onadata.apps.api.models.project_xform import ProjectXForm
from onadata.apps.api.models.team import Team
from onadata.apps.main.forms import QuickConverter
from onadata.apps.odk_logger.models.xform import XForm
from onadata.apps.odk_viewer.models.parsed_instance import ParsedInstance,\
    datetime_from_str, _encode_for_mongo
from onadata.libs.utils.logger_tools import publish_form
from onadata.libs.utils.user_auth import check_and_set_form_by_id, \
    check_and_set_form_by_id_string

DECIMAL_PRECISION = 2


def _dictfetchall(cursor):
    "Returns all rows from a cursor as a dict"
    desc = cursor.description
    return [
        dict(zip([col[0] for col in desc], row))
        for row in cursor.fetchall()
    ]


def _get_first_last_names(name):
    name_split = name.split()
    first_name = name_split[0]
    last_name = u''
    if len(name_split) > 1:
        last_name = u' '.join(name_split[1:])
    return first_name, last_name


def _get_id_for_type(record, mongo_field):
    date_field = datetime_from_str(record[mongo_field])
    mongo_str = '$' + mongo_field

    return {"$substr": [mongo_str, 0, 10]} if isinstance(date_field, datetime)\
        else mongo_str


@property
def using_postgres():
    return settings.DATABASES[
        'default']['ENGINE'] == 'django.db.backends.postgresql_psycopg2'


def _count_group(table, field, name):
    if using_postgres:
        result = _postgres_count_group(table, field, name)
    else:
        raise Exception("Unsopported Database")
    return result


def _postgres_count_group(table, field, name):
    json_query = "json->>'%s'" % field
    string_args = {
        'table': table,
        'json': json_query,
        'name': name
    }

    return "SELECT %(json)s AS %(name)s, COUNT(%(json)s) AS count FROM "\
           "%(table)s GROUP BY %(json)s" % string_args


def get_accessible_forms(owner=None):
    return XForm.objects.filter(user__username=owner).distinct()


def create_organization(name, creator):
    """
    Organization created by a user
    - create a team, OwnerTeam with full permissions to the creator
        - Team(name='Owners', organization=organization).save()

    """
    organization = User.objects.create(username=name)
    organization_profile = OrganizationProfile.objects.create(
        user=organization, creator=creator)
    return organization_profile


def create_organization_object(org_name, creator, attrs={}):
    '''Creates an OrganizationProfile object without saving to the database'''
    name = attrs.get('name', org_name)
    first_name, last_name = _get_first_last_names(name)
    new_user = User(username=org_name, first_name=first_name,
                    last_name=last_name, email=attrs.get('email', u''))
    new_user.save()
    profile = OrganizationProfile(
        user=new_user, name=name, creator=creator,
        created_by=creator,
        city=attrs.get('city', u''),
        country=attrs.get('country', u''),
        organization=attrs.get('organization', u''),
        home_page=attrs.get('home_page', u''),
        twitter=attrs.get('twitter', u''))
    return profile


def create_organization_team(organization, name, permission_names=[]):
    team = Team.objects.create(organization=organization, name=name)
    content_type = ContentType.objects.get(
        app_label='api', model='organizationprofile')
    if permission_names:
        # get permission objects
        perms = Permission.objects.filter(
            codename__in=permission_names, content_type=content_type)
        if perms:
            team.permissions.add(*tuple(perms))
    return team


def add_user_to_team(team, user):
    user.groups.add(team)


def create_organization_project(organization, project_name, created_by):
    """Creates a project for a given organization
    :param organization: User organization
    :param project_name
    :param created_by: User with permissions to create projects within the
                       organization

    :returns: a Project instance
    """
    profile = OrganizationProfile.objects.get(user=organization)

    if not profile.is_organization_owner(created_by):
        return None

    project = Project.objects.create(name=project_name,
                                     organization=organization,
                                     created_by=created_by)

    return project


def add_team_to_project(team, project):
    """Adds a  team to a project

    :param team:
    :param project:

    :returns: True if successful or project has already been added to the team
    """
    if isinstance(team, Team) and isinstance(project, Project):
        if not team.projects.filter(pk=project.pk):
            team.projects.add(project)
        return True
    return False


def add_xform_to_project(xform, project, creator):
    """Adds an xform to a project"""
    instance = ProjectXForm.objects.create(
        xform=xform, project=project, created_by=creator)
    instance.save()
    return instance


def publish_project_xform(request, project):
    def set_form():
        form = QuickConverter(request.POST, request.FILES)
        return form.publish(project.organization)
    xform = publish_form(set_form)
    if isinstance(xform, XForm):
        add_xform_to_project(xform, project, request.user)
    return xform


def get_form_submissions_grouped_by_field(xform, field, name=None):
    """Number of submissions grouped by field"""
    cursor = connection.cursor()

    if not name:
        name = field

    cursor.execute(_count_group('odk_logger_instance', field, name))
    result = _dictfetchall(cursor)

    if result[0][name] is None:
        raise ValueError(_(u"Field '%s' does not exist." % field))

    return result


def get_field_records(field, xform):
    username = xform.user.username
    id_string = xform.id_string
    query = None
    sort = None
    query = {}
    mongo_field = _encode_for_mongo(field)
    query[mongo_field] = {"$exists": True}
    sort = {mongo_field: 1}

    # check if requested field a datetime str
    fields = [mongo_field]

    return ParsedInstance.query_mongo(username, id_string, query, fields, sort)


def mode(a, axis=0):
    """
    Adapted from
    https://github.com/scipy/scipy/blob/master/scipy/stats/stats.py#L568
    """
    a, axis = _chk_asarray(a, axis)
    scores = np.unique(np.ravel(a))       # get ALL unique values
    testshape = list(a.shape)
    testshape[axis] = 1
    oldmostfreq = np.zeros(testshape)
    oldcounts = np.zeros(testshape)
    for score in scores:
        template = (a == score)
        counts = np.expand_dims(np.sum(template, axis), axis)
        mostfrequent = np.where(counts > oldcounts, score, oldmostfreq)
        oldcounts = np.maximum(counts, oldcounts)
        oldmostfreq = mostfrequent
    return mostfrequent, oldcounts


def _chk_asarray(a, axis):
    if axis is None:
        a = np.ravel(a)
        outaxis = 0
    else:
        a = np.asarray(a)
        outaxis = axis
    return a, outaxis


def get_numeric_fields(xform):
    """List of numeric field names for specified xform"""
    k = []
    dd = xform.data_dictionary()
    survey_elements = dd.get_survey_elements_of_type('integer') +\
        dd.get_survey_elements_of_type('decimal')

    for element in survey_elements:
        name = element.get_abbreviated_xpath()
        k.append(name)

    return k


def get_median_for_field(field, xform):
    cursor = get_field_records(field, xform)
    mongo_field = _encode_for_mongo(field)
    return np.median([float(i[mongo_field]) for i in cursor])


def get_median_for_numeric_fields_in_form(xform, field=None):
    data = {}
    for field_name in [field] if field else get_numeric_fields(xform):
        median = get_median_for_field(field_name, xform)
        data.update({field_name: median})
    return data


def get_mean_for_field(field, xform):
    cursor = get_field_records(field, xform)
    mongo_field = _encode_for_mongo(field)
    return np.mean([float(i[mongo_field]) for i in cursor])


def get_mean_for_numeric_fields_in_form(xform, field):
    data = {}
    for field_name in [field] if field else get_numeric_fields(xform):
        mean = get_mean_for_field(field_name, xform)
        data.update({field_name: round(mean, DECIMAL_PRECISION)})
    return data


def get_mode_for_field(field, xform):
    cursor = get_field_records(field, xform)
    mongo_field = _encode_for_mongo(field)
    a = np.array([float(i[mongo_field]) for i in cursor])
    m, count = mode(a)
    return m


def get_mode_for_numeric_fields_in_form(xform, field=None):
    data = {}
    for field_name in [field] if field else get_numeric_fields(xform):
        mode = get_mode_for_field(field_name, xform)
        data.update({field_name: round(mode, DECIMAL_PRECISION)})
    return data


def get_min_max_range_for_field(field, xform):
    cursor = get_field_records(field, xform)
    mongo_field = _encode_for_mongo(field)
    a = np.array([float(i[mongo_field]) for i in cursor])
    _max = np.max(a)
    _min = np.min(a)
    _range = _max - _min
    return _min, _max, _range


def get_min_max_range(xform, field=None):
    data = {}
    for field_name in [field] if field else get_numeric_fields(xform):
        _min, _max, _range = get_min_max_range_for_field(field_name, xform)
        data[field_name] = {'max': _max, 'min': _min, 'range': _range}
    return data


def get_all_stats(xform, field=None):
    data = {}
    for field_name in [field] if field else get_numeric_fields(xform):
        _min, _max, _range = get_min_max_range_for_field(field_name, xform)
        mode = get_mode_for_field(field_name, xform)
        mean = get_mean_for_field(field_name, xform)
        median = get_median_for_field(field_name, xform)
        data[field_name] = {
            'mean': round(mean, DECIMAL_PRECISION),
            'median': median,
            'mode': round(mode, DECIMAL_PRECISION),
            'max': _max,
            'min': _min,
            'range': _range
        }
    return data


def get_xform(formid, request):
    try:
        formid = int(formid)
    except ValueError:
        xform = check_and_set_form_by_id_string(formid, request)
    else:
        xform = check_and_set_form_by_id(int(formid), request)

    if not xform:
        raise exceptions.PermissionDenied(_(
            "You do not have permission to view data from this form."))

    return xform
