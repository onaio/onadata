
from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy as _

# WE SHOULD PUT MORE STRUCTURE ON THESE TAGS SO WE CAN ACCESS DOCUMENT
# FIELDS ELEGANTLY

# These are common variable tags that we'll want to access
INSTANCE_DOC_NAME = "_name"
ID = "_id"
UUID = "_uuid"
PICTURE = "picture"
GPS = "location/gps"
SURVEY_TYPE = '_survey_type_slug'

# Phone IMEI:
DEVICE_ID = "device_id"  # This tag was used in Phase I
IMEI = "imei"  # This tag was used in Phase II
# Survey start time:
START_TIME = "start_time"  # This tag was used in Phase I
START = "start"  # This tag was used in Phase II
END_TIME = "end_time"
END = "end"

# value of INSTANCE_DOC_NAME that indicates a regisration form
REGISTRATION = "registration"
# keys that we'll look for in the registration form
NAME = "name"

# extra fields that we're adding to our mongo doc
XFORM_ID_STRING = "_xform_id_string"
XFORM_ID = "_xform_id"
STATUS = "_status"
ATTACHMENTS = "_attachments"
UUID = "_uuid"
USERFORM_ID = "_userform_id"
DATE = "_date"
GEOLOCATION = "_geolocation"
SUBMISSION_TIME = '_submission_time'
DELETEDAT = "_deleted_at"  # marker for delete surveys
BAMBOO_DATASET_ID = "_bamboo_dataset_id"
SUBMITTED_BY = "_submitted_by"
VERSION = "_version"
DURATION = "_duration"

# fields to deal with media attachments and keep track of how many
# have been received
MEDIA_ALL_RECEIVED = "_media_all_received"
TOTAL_MEDIA = "_total_media"
MEDIA_COUNT = "_media_count"

INSTANCE_ID = "instanceID"
META_INSTANCE_ID = "meta/instanceID"
INDEX = "_index"
PARENT_INDEX = "_parent_index"
PARENT_TABLE_NAME = "_parent_table_name"

# instance flags
EDITED = "_edited"
LAST_EDITED = "_last_edited"
# datetime format that we store in mongo
MONGO_STRFTIME = '%Y-%m-%dT%H:%M:%S'
DATE_FORMAT = '%Y-%m-%d'

# how to represent N/A in exports
NA_REP = 'n/a'

# hold tags
TAGS = "_tags"

NOTES = "_notes"
REVIEW_STATUS = "_review_status"
REVIEW_COMMENT = "_review_comment"

# statistics
MEAN = "mean"
MIN = "min"
MAX = "max"
RANGE = "range"
MEDIAN = "median"
MODE = "mode"

TEXTIT = 'textit'
OSM = 'osm'
MULTIPLE_SELECT_TYPE = 'select all that apply'
GROUPNAME_REMOVED_FLAG = 'group-name-removed'
DATAVIEW_EXPORT = U'dataview'
OWNER_TEAM_NAME = "Owners"

API_TOKEN = 'api-token'
KNOWN_MEDIA_TYPES = ['photo', 'image', 'audio', 'video']
NUMERIC_LIST = ['integer', 'decimal', 'calculate']
SELECT_ONE = 'select one'

# google_sheets
GOOGLE_SHEET = 'google_sheets'
GOOGLE_SHEET_ID = 'GOOGLE_SHEET_ID'
GOOGLE_SHEET_TITLE = 'GOOGLE_SHEET_TITLE'
GOOGLE_SHEET_DATA_TYPE = 'google_sheets'
UPDATE_OR_DELETE_GOOGLE_SHEET_DATA = 'UPDATE_OR_DELETE_GOOGLE_SHEET_DATA'
SYNC_EXISTING_DATA = "send_existing_data"
USER_ID = 'USER_ID'

# tag group delimiter name
GROUP_DELIMETER_TAG = 'group_delimiter'
XFORM_META_PERMS = 'xform_meta_perms'

# index tag
REPEAT_INDEX_TAGS = 'repeat_index_tags'

# SAV
# VarTyoes: 0 means 'numeric', and varType > 0 means 'character' of that length
# (in bytes)
SAV_NUMERIC_TYPE = 0
SAV_255_BYTES_TYPE = 255

EXPORT_MIMES = {
    'xls': 'vnd.ms-excel',
    'xlsx': 'vnd.openxmlformats',
    'csv': 'csv',
    'zip': 'zip',
    'csv_zip': 'zip',
    'sav_zip': 'zip',
    'sav': 'sav',
    'kml': 'vnd.google-earth.kml+xml',
    OSM: OSM
}

# Submission Review Tags
COMMENT_REQUIRED = _('Cannot reject a submission without a comment.')
SUBMISSION_REVIEW_INSTANCE_FIELD = '_review_status'
EXCEL_TRUE = 1
EXCEL_FALSE = 0
MEMBERS = 'members'
XLS_DATE_FIELDS = ['date', 'today']
SUBMISSION_REVIEW = 'submission_review'
