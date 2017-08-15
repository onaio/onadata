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
XFORM_ID = u"_xform_id"
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

# fields to deal with media attachments and keep track of how many
# have been received
MEDIA_ALL_RECEIVED = u"_media_all_received"
TOTAL_MEDIA = u"_total_media"
MEDIA_COUNT = u"_media_count"

INSTANCE_ID = u"instanceID"
META_INSTANCE_ID = u"meta/instanceID"
INDEX = u"_index"
PARENT_INDEX = u"_parent_index"
PARENT_TABLE_NAME = u"_parent_table_name"

# instance flags
EDITED = "_edited"
LAST_EDITED = "_last_edited"
# datetime format that we store in mongo
MONGO_STRFTIME = '%Y-%m-%dT%H:%M:%S'
DATE_FORMAT = '%Y-%m-%d'

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
DATAVIEW_EXPORT = U'dataview'
OWNER_TEAM_NAME = "Owners"

API_TOKEN = 'api-token'
KNOWN_MEDIA_TYPES = ['photo', 'image', 'audio', 'video']
NUMERIC_LIST = [u'integer', u'decimal', u'calculate']
SELECT_ONE = u'select one'

# google_sheets
GOOGLE_SHEET = u'google_sheets'
GOOGLE_SHEET_ID = u'GOOGLE_SHEET_ID'
GOOGLE_SHEET_TITLE = u'GOOGLE_SHEET_TITLE'
GOOGLE_SHEET_DATA_TYPE = u'google_sheets'
UPDATE_OR_DELETE_GOOGLE_SHEET_DATA = u'UPDATE_OR_DELETE_GOOGLE_SHEET_DATA'
SYNC_EXISTING_DATA = u"send_existing_data"
USER_ID = u'USER_ID'

# tag group delimiter name
GROUP_DELIMETER_TAG = 'group_delimiter'
XFORM_META_PERMS = u'xform_meta_perms'
