import cStringIO
import json
from collections import defaultdict
from datetime import datetime

from celery import current_task
from django.contrib.auth.models import User

from onadata.apps.logger.models import Instance
from onadata.libs.utils.async_status import FAILED, async_status
from onadata.libs.utils.common_tags import MULTIPLE_SELECT_TYPE
from onadata.libs.utils.csv_import import (dict2xmlsubmission, dict_merge,
                                           get_submission_meta_dict)
from onadata.libs.utils.dict_tools import csv_dict_to_nested_dict
from onadata.libs.utils.logger_tools import safe_create_instance


def submit_json(username, xform, import_file):
    """ Imports JSON data to an existing form

    Takes a JSON formatted file or string containing rows of submission
    and converts those to xml submissions and finally submits them by calling
    :py:func:`onadata.libs.utils.logger_tools.safe_create_instance`

    :param str username: the subission user
    :param onadata.apps.logger.models.XForm xfrom: The submission's XForm.
    :param (str or file): A JSON formatted file with submission rows.
    :return: If sucessful, a dict with import summary else dict with error str.
    :rtype: Dict
    """
    if isinstance(import_file, unicode):
        import_file = cStringIO.StringIO(import_file)
    elif import_file is None or not hasattr(import_file, 'read'):
        return async_status(FAILED, (u'Invalid param type for `import_file`. '
                                     'Expected utf-8 encoded file or unicode'
                                     ' string got {} instead.'
                                     .format(type(import_file).__name__)))

    json_data = json.load(import_file)
    num_rows = json_data.__len__()

    # get headers from first row
    first_row = json_data[0]
    headers = first_row.keys()

    # Get the data dictionary
    xform_header = xform.get_headers()

    missing_col = set(xform_header).difference(headers)
    addition_col = set(headers).difference(xform_header)

    # change to list
    missing_col = list(missing_col)
    addition_col = list(addition_col)
    # remove all metadata columns
    missing = [col for col in missing_col if not col.startswith("_")]

    # remove all meta/instanceid columns

    while 'meta/instanceID' in missing:
        missing.remove('meta/instanceID')

    # remove all metadata inside groups
    missing = [col for col in missing if not ("/_" in col)]

    # ignore if is multiple select question
    for col in headers:
        # this col is a multiple select question
        survey_element = xform.get_survey_element(col)
        if survey_element and \
                survey_element.get('type') == MULTIPLE_SELECT_TYPE:
            # remove from the missing and additional list
            missing = [x for x in missing if not x.startswith(col)]

            addition_col.remove(col)

    # remove headers for repeats that might be missing from json
    missing = [m for m in missing if m.find('[') == -1]

    # Include additional repeats
    addition_col = [a for a in addition_col if a.find('[') == -1]

    if missing:
        return async_status(FAILED,
                            u"Sorry uploaded file does not match the form. "
                            u"The file is missing the column(s): "
                            u"{0}.".format(', '.join(missing)))

    rollback_uuids = []
    submission_time = datetime.utcnow().isoformat()
    ona_uuid = {'formhub': {'uuid': xform.uuid}}
    error = None
    additions = inserts = 0
    try:
        for row in json_data:
            # remove the additional columns
            for index in addition_col:
                del row[index]

            # fetch submission uuid before purging row metadata
            row_uuid = row.get('_uuid')
            submitted_by = row.get('_submitted_by')
            submission_date = row.get('_submission_time', submission_time)

            location_data = {}
            for key in row.keys():  # seems faster than a comprehension
                # remove metadata (keys starting with '_')
                if key.startswith('_'):
                    del row[key]

                # Collect row location data into separate location_data dict
                if key.endswith(('.latitude', '.longitude', '.altitude',
                                 '.precision')):
                    location_key, location_prop = key.rsplit(u'.', 1)
                    location_data.setdefault(location_key, {}).update(
                        {
                            location_prop: row.get(key, '0')
                        })
                # remove 'n/a' values
                if not key.startswith('_') and row[key] == 'n/a':
                    del row[key]

            # collect all location K-V pairs into single geopoint field(s)
            # in location_data dict
            for location_key in location_data.keys():
                location_data.update({
                    location_key: (u'%(latitude)s %(longitude)s '
                                   '%(altitude)s %(precision)s') %
                    defaultdict(lambda: '', location_data.get(location_key))
                })

            row = csv_dict_to_nested_dict(row)
            location_data = csv_dict_to_nested_dict(location_data)

            row = dict_merge(row, location_data)

            # inject our form's uuid into the submission
            row.update(ona_uuid)

            old_meta = row.get('meta', {})
            new_meta, update = get_submission_meta_dict(xform, row_uuid)
            inserts += update
            old_meta.update(new_meta)
            row.update({'meta': old_meta})

            row_uuid = row.get('meta').get('instanceID')
            rollback_uuids.append(row_uuid.replace('uuid:', ''))

            xml_file = cStringIO.StringIO(
                dict2xmlsubmission(row, xform, row_uuid, submission_date))

            try:
                error, instance = safe_create_instance(username, xml_file, [],
                                                       xform.uuid, None)
            except ValueError as e:
                error = e

            if error:
                Instance.objects.filter(
                    uuid__in=rollback_uuids, xform=xform).delete()
                return async_status(FAILED, str(error))
            else:
                additions += 1
                try:
                    current_task.update_state(
                        state='PROGRESS',
                        meta={
                            'progress': additions,
                            'total': num_rows,
                            'info': addition_col
                        })
                except:
                    pass

                users = User.objects.filter(
                    username=submitted_by) if submitted_by else []
                if users:
                    instance.user = users[0]
                    instance.save()

    except UnicodeDecodeError:
        Instance.objects.filter(uuid__in=rollback_uuids, xform=xform).delete()
        return async_status(FAILED, u'JSON file must be utf-8 encoded')
    except Exception as e:
        Instance.objects.filter(uuid__in=rollback_uuids, xform=xform).delete()
        return async_status(FAILED, str(e))

    return {
        u"additions":
        additions - inserts,
        u"updates":
        inserts,
        u"info":
        u"Additional column(s) excluded from the upload: '{0}'."
        .format(', '.join(list(addition_col)))
    }
