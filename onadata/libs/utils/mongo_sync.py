import sys

from django.conf import settings
from pymongo import MongoClient

from onadata.apps.logger.models import Instance
from onadata.apps.logger.models import XForm
from onadata.apps.viewer.models import ParsedInstance
from onadata.libs.utils import common_tags
from onadata.libs.utils.model_tools import queryset_iterator


def get_mongo_connection():
    MONGO_DATABASE = settings.MONGO_DATABASE
    if MONGO_DATABASE.get('USER') and MONGO_DATABASE.get('PASSWORD'):
        MONGO_CONNECTION_URL = (
            "mongodb://%(USER)s:%(PASSWORD)s@%(HOST)s:%(PORT)s") \
            % MONGO_DATABASE
    else:
        MONGO_CONNECTION_URL = "mongodb://%(HOST)s:%(PORT)s" % MONGO_DATABASE

    MONGO_CONNECTION = MongoClient(
        MONGO_CONNECTION_URL, safe=True, j=True, tz_aware=True)
    return MONGO_CONNECTION[MONGO_DATABASE['NAME']]


def update_mongo_for_xform(xform, only_update_missing=True):
    mongo_instances = get_mongo_connection().instances
    instance_ids = set(
        [i.id for i in Instance.objects.only('id').filter(xform=xform)])
    sys.stdout.write("Total no of instances: %d\n" % len(instance_ids))
    mongo_ids = set()
    user = xform.user
    userform_id = "%s_%s" % (user.username, xform.id_string)
    if only_update_missing:
        sys.stdout.write("Only updating missing mongo instances\n")
        mongo_ids = set(
            [rec[common_tags.ID] for rec in mongo_instances.find(
                {common_tags.USERFORM_ID: userform_id},
                {common_tags.ID: 1})])
        sys.stdout.write("Total no of mongo instances: %d\n" % len(mongo_ids))
        # get the difference
        instance_ids = instance_ids.difference(mongo_ids)
    else:
        # clear mongo records
        mongo_instances.remove({common_tags.USERFORM_ID: userform_id})
    # get instances
    sys.stdout.write(
        "Total no of instances to update: %d\n" % len(instance_ids))
    instances = Instance.objects.only('id').in_bulk(
        [id for id in instance_ids])
    total = len(instances)
    done = 0
    for id, instance in instances.items():
        (pi, created) = ParsedInstance.objects.get_or_create(instance=instance)
        pi.save(async=False)
        done += 1
        # if 1000 records are done, flush mongo
        if (done % 1000) == 0:
            sys.stdout.write(
                'Updated %d records, flushing MongoDB...\n' % done)
        settings.MONGO_CONNECTION.admin.command({'fsync': 1})
        progress = "\r%.2f %% done..." % ((float(done) / float(total)) * 100)
        sys.stdout.write(progress)
        sys.stdout.flush()
    # flush mongo again when done
    settings.MONGO_CONNECTION.admin.command({'fsync': 1})
    sys.stdout.write(
        "\nUpdated %s\n------------------------------------------\n"
        % xform.id_string)


def mongo_sync_status(remongo=False, update_all=False, user=None, xform=None):
    """Check the status of records in the mysql db versus mongodb. At a
    minimum, return a report (string) of the results.

    Optionally, take action to correct the differences, based on these
    parameters, if present and defined:

    remongo    -> if True, update the records missing in mongodb
    (default: False)

    update_all -> if True, update all the relevant records (default: False)
    user       -> if specified, apply only to the forms for the given user
    (default: None)

    xform      -> if specified, apply only to the given form (default: None)
    """
    mongo_instances = get_mongo_connection().instances

    qs = XForm.objects.only('id_string', 'user').select_related('user')
    if user and not xform:
        qs = qs.filter(user=user)
    elif user and xform:
        qs = qs.filter(user=user, id_string=xform.id_string)
    else:
        qs = qs.all()

    total = qs.count()
    found = 0
    done = 0
    total_to_remongo = 0
    report_string = ""
    for xform in queryset_iterator(qs, 100):
        # get the count
        user = xform.user
        instance_count = Instance.objects.filter(xform=xform).count()
        userform_id = "%s_%s" % (user.username, xform.id_string)
        mongo_count = mongo_instances.find(
            {common_tags.USERFORM_ID: userform_id}).count()

        if instance_count != mongo_count or update_all:
            line = "user: %s, id_string: %s\nInstance count: %d\t"\
                   "Mongo count: %d\n---------------------------------"\
                   "-----\n" % (
                       user.username, xform.id_string, instance_count,
                       mongo_count)
            report_string += line
            found += 1
            total_to_remongo += (instance_count - mongo_count)

            # should we remongo
            if remongo or (remongo and update_all):
                if update_all:
                    sys.stdout.write(
                        "Updating all records for %s\n--------------------"
                        "---------------------------\n" % xform.id_string)
                else:
                    sys.stdout.write(
                        "Updating missing records for %s\n----------------"
                        "-------------------------------\n"
                        % xform.id_string)
                update_mongo_for_xform(
                    xform, only_update_missing=not update_all)
        done += 1
        sys.stdout.write(
            "%.2f %% done ...\r" % ((float(done) / float(total)) * 100))
    # only show stats if we are not updating mongo, the update function
    # will show progress
    if not remongo:
        line = "Total # of forms out of sync: %d\n" \
            "Total # of records to remongo: %d\n" % (found, total_to_remongo)
        report_string += line
    return report_string
