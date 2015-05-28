# WE SHOULD PUT MORE STRUCTURE ON THESE TAGS SO WE CAN ACCESS DOCUMENT
# FIELDS ELEGANTLY

# These are common variable tags that we'll want to access
INSTANCE_DOC_NAME = u"_name"
ID = u"_id"
UUID = u"_uuid"
PICTURE = u"picture"
GPS = u"location/gps"
SURVEY_TYPE = u'_survey_type_slug'

# Phone IMEI:
DEVICE_ID = u"device_id"  # This tag was used in Phase I
IMEI = u"imei"            # This tag was used in Phase II
# Survey start time:
START_TIME = u"start_time"  # This tag was used in Phase I
START = u"start"            # This tag was used in Phase II
END_TIME = u"end_time"
END = u"end"

# value of INSTANCE_DOC_NAME that indicates a regisration form
REGISTRATION = u"registration"
# keys that we'll look for in the registration form
NAME = u"name"

# extra fields that we're adding to our mongo doc
XFORM_ID_STRING = u"_xform_id_string"
STATUS = u"_status"
ATTACHMENTS = u"_attachments"
UUID = u"_uuid"
USERFORM_ID = u"_userform_id"
DATE = u"_date"
GEOLOCATION = u"_geolocation"
SUBMISSION_TIME = u'_submission_time'
DELETEDAT = u"_deleted_at"  # marker for delete surveys
BAMBOO_DATASET_ID = u"_bamboo_dataset_id"
SUBMITTED_BY = u"_submitted_by"
VERSION = u"_version"
DURATION = u"_duration"

INSTANCE_ID = u"instanceID"
META_INSTANCE_ID = u"meta/instanceID"
INDEX = u"_index"
PARENT_INDEX = u"_parent_index"
PARENT_TABLE_NAME = u"_parent_table_name"

# datetime format that we store in mongo
MONGO_STRFTIME = '%Y-%m-%dT%H:%M:%S'

# how to represent N/A in exports
NA_REP = 'n/a'

# hold tags
TAGS = u"_tags"

NOTES = u"_notes"

# statistics
MEAN = u"mean"
MIN = u"min"
MAX = u"max"
RANGE = u"range"
MEDIAN = u"median"
MODE = u"mode"

TEXTIT = u'textit'
OSM = u'osm'
MULTIPLE_SELECT_TYPE = u'select all that apply'
GROUPNAME_REMOVED_FLAG = u'group-name-removed'
