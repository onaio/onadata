# -*- coding: utf-8 -*-
"""
Common tags.
"""

from __future__ import unicode_literals

from django.utils.translation import gettext_lazy as _

# WE SHOULD PUT MORE STRUCTURE ON THESE TAGS SO WE CAN ACCESS DOCUMENT
# FIELDS ELEGANTLY

# These are common variable tags that we'll want to access
INSTANCE_DOC_NAME = "_name"
ID = "_id"
PARENT_TABLE = "__parent_table"
PARENT_ID = "__parent_id"
UUID = "_uuid"
PICTURE = "picture"
GPS = "location/gps"
SURVEY_TYPE = "_survey_type_slug"

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
SUBMISSION_TIME = "_submission_time"
DELETEDAT = "_deleted_at"  # marker for delete surveys
BAMBOO_DATASET_ID = "_bamboo_dataset_id"
SUBMITTED_BY = "_submitted_by"
VERSION = "_version"
DURATION = "_duration"
DECRYPTION_ERROR = "_decryption_error"

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

# Instance last modified field
# The 'date_modified' is a Django auto updated timestamp
# that's updated every time an Instance object is saved.
DATE_MODIFIED = "_date_modified"
# instance flags
EDITED = "_edited"
LAST_EDITED = "_last_edited"
# datetime format that we store in mongo
MONGO_STRFTIME = "%Y-%m-%dT%H:%M:%S"
DATE_FORMAT = "%Y-%m-%d"
KNOWN_DATE_FORMATS = [
    DATE_FORMAT,
    MONGO_STRFTIME,
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f%z",
]

# how to represent N/A in exports
NA_REP = "n/a"

# hold tags
TAGS = "_tags"

NOTES = "_notes"
REVIEW_STATUS = "_review_status"
REVIEW_COMMENT = "_review_comment"
REVIEW_DATE = "_review_date"

# statistics
MEAN = "mean"
MIN = "min"
MAX = "max"
RANGE = "range"
MEDIAN = "median"
MODE = "mode"

TEXTIT = "textit"
TEXTIT_DETAILS = "textit_details"
OSM = "osm"
SELECT_BIND_TYPE = "string"
MULTIPLE_SELECT_TYPE = "select all that apply"
REPEAT_SELECT_TYPE = "repeat"
GROUPNAME_REMOVED_FLAG = "group-name-removed"
DATAVIEW_EXPORT = "dataview"
OWNER_TEAM_NAME = "Owners"

API_TOKEN = "api-token"  # nosec
ONADATA_KOBOCAT_AUTH_HEADER = "X-ONADATA-KOBOCAT-AUTH"
KNOWN_MEDIA_TYPES = ["photo", "image", "audio", "video", "file"]
MEDIA_FILE_TYPES = {
    "image": ["image/png", "image/jpeg", "image/jpg"],
    "audio": ["audio/mp3", "audio/mp4"],
    "video": ["video/mp4"],
    "document": [
        "application/pdf",
        "text/plain",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.\
            document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/json",
        "application/geo+json",
        "application/msword",
        "application/vnd.ms-excel",
        "application/vnd.ms-powerpoint",
        "application/vnd.oasis.opendocument.text",
        "application/vnd.oasis.opendocument.spreadsheet",
        "application/vnd.oasis.opendocument.presentation",
        "application/vnd.openxmlformats-officedocument.presentationml.\
        presentation",
        "application/zip",
    ],
}

NUMERIC_LIST = ["integer", "decimal", "calculate"]
SELECT_ONE = "select one"

# google_sheets
GOOGLE_SHEET = "google_sheets"
GOOGLE_SHEET_ID = "GOOGLE_SHEET_ID"
GOOGLE_SHEET_TITLE = "GOOGLE_SHEET_TITLE"
GOOGLE_SHEET_DATA_TYPE = "google_sheets"
UPDATE_OR_DELETE_GOOGLE_SHEET_DATA = "UPDATE_OR_DELETE_GOOGLE_SHEET_DATA"
SYNC_EXISTING_DATA = "send_existing_data"
USER_ID = "USER_ID"

# tag group delimiter name
GROUP_DELIMETER_TAG = "group_delimiter"
XFORM_META_PERMS = "xform_meta_perms"

# index tag
REPEAT_INDEX_TAGS = "repeat_index_tags"

# SAV
# VarTyoes: 0 means 'numeric', and varType > 0 means 'character' of that length
# (in bytes)
SAV_NUMERIC_TYPE = 0
SAV_255_BYTES_TYPE = 255

EXPORT_MIMES = {
    "xls": "vnd.ms-excel",
    "xlsx": "vnd.openxmlformats",
    "csv": "csv",
    "zip": "zip",
    "csv_zip": "zip",
    "sav_zip": "zip",
    "sav": "sav",
    "kml": "vnd.google-earth.kml+xml",
    OSM: OSM,
}

# Submission Review Tags
COMMENT_REQUIRED = _("Cannot reject a submission without a comment.")
SUBMISSION_REVIEW_INSTANCE_FIELD = "_review_status"
EXCEL_TRUE = 1
EXCEL_FALSE = 0
MEMBERS = "members"
XLS_DATE_FIELDS = ["date", "today"]
SUBMISSION_REVIEW = "submission_review"
IMPORTED_VIA_CSV_BY = "imported_via_csv_by"
XLS_DATETIME_FIELDS = ["start", "end", "dateTime", "_submission_time"]

METADATA_FIELDS = [
    REVIEW_COMMENT,
    REVIEW_STATUS,
    STATUS,
    EDITED,
    VERSION,
    DURATION,
    NOTES,
    UUID,
    TAGS,
    BAMBOO_DATASET_ID,
    ATTACHMENTS,
    GEOLOCATION,
    MEDIA_COUNT,
    TOTAL_MEDIA,
    SUBMITTED_BY,
    MEDIA_ALL_RECEIVED,
    XFORM_ID_STRING,
    SUBMISSION_TIME,
    XFORM_ID,
    DATE_MODIFIED,
]

INSTANCE_CREATE_EVENT = "Submission created"
INSTANCE_UPDATE_EVENT = "Submission updated"
XFORM_CREATION_EVENT = "XForm created"
PROJECT_CREATION_EVENT = "Project created"
USER_CREATION_EVENT = "User account created"
DECRYPTION_FAILURE_MAX_RETRIES = "MAX_RETRIES_EXCEEDED"
DECRYPTION_FAILURE_KEY_DISABLED = "KMS_KEY_DISABLED"
DECRYPTION_FAILURE_KEY_NOT_FOUND = "KMS_KEY_NOT_FOUND"
DECRYPTION_FAILURE_INVALID_SUBMISSION = "INVALID_SUBMISSION"
DECRYPTION_FAILURE_INSTANCE_NOT_ENCRYPTED = "INSTANCE_NOT_ENCRYPTED"
DECRYPTION_FAILURE_ENCRYPTION_UNMANAGED = "ENCRYPTION_UNMANAGED"
DECRYPTION_FAILURE_MESSAGES = {
    DECRYPTION_FAILURE_MAX_RETRIES: _(
        "System was unable to decrypt the submission after multiple attempts."
    ),
    DECRYPTION_FAILURE_KEY_DISABLED: _("KMSKey is disabled."),
    DECRYPTION_FAILURE_KEY_NOT_FOUND: _("KMSKey used for encryption not found."),
    DECRYPTION_FAILURE_INVALID_SUBMISSION: _("Corrupted data."),
    DECRYPTION_FAILURE_INSTANCE_NOT_ENCRYPTED: _("Instance is not encrypted."),
    DECRYPTION_FAILURE_ENCRYPTION_UNMANAGED: _("Encryption is not using managed keys."),
}
EXPORT_OPTION_GEO_FIELD = "geo_field"
EXPORT_OPTION_SIMPLE_STYLE = "simple_style"
EXPORT_OPTION_TITLE = "title"
EXPORT_OPTION_FIELDS = "fields"
GEOJSON_EXTRA_DATA_EXPORT_OPTION_MAP = {
    "data_geo_field": EXPORT_OPTION_GEO_FIELD,
    "data_simple_style": EXPORT_OPTION_SIMPLE_STYLE,
    "data_title": EXPORT_OPTION_TITLE,
    "data_fields": EXPORT_OPTION_FIELDS,
}
