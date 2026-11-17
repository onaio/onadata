
package config;

import static config.ConfigProperties.username;
import static config.EnvGlobals.orgUserName;

public class EndpointURLs {

    public static String GET_DATA = "/api/v1/data/";
    public static String GET_TOKEN = "/api/v1/user";
    public static String IMPORT_DATA_CSV = "/api/v1/forms/{id}/csv_import";
    public static String GET_DATA_USING_START_VALUE = "/api/v1/data/{id}?start=2";
    public static String GET_DATA_BY_COLUMN  = "/api/v1/data/{id}.json?fields=[\"_id\", \"_last_edited\"]";
    public static String GET_DATA_USING_START_LIMIT = "/api/v1/data/{id}?start=2&limit=4";
    public static String GET_ALL_DATA_CSV_FORMAT = "/api/v1/data.csv";
    public static String GET_DATA_CSV_FORMAT = "/api/v1/data/{id}.csv";
    public static String GET_JSON_DATA_SPECIFIC_FORM = "/api/v1/data/";
    public static String GET_XML_DATA_SPECIFIC_FORM = "/api/v1/data/{id}.xml";
    public static String GET_DATA_BY_PAGINATION= "/api/v1/data/{id}.json?page=1&page_size=10";
    public static String GET_SORT_DATA_ASC_ORDER = "/api/v1/data/{id}.json?sort=\"resp_age\":1";
    public static String GET_SORT_DATA_DESC_ORDER = "/api/v1/data/{id}.json?sort=\"resp_age\":-1";
    public static String GET_SINGLE_DATA_SUBMISSION_FOR_FORM = "/api/v1/data/{id}/";
    public static String GET_DATA_HISTORY = "/api/v1/data/{id}/{id2}/history";
    public static String GET_DATA_BY_APPROVED_STATUS = "/api/v1/data/{id}.json?query=\"_review_status\" : 1";
    public static String GET_DATA_BY_REJECTED_STATUS = "/api/v1/data/{id}.json?query=\"_review_status\" : 2";
    public static String GET_DATA_BY_PENDING_STATUS = "/api/v1/data/{id}.json?query=\"_review_status\" : null";
    public static String GET_DATA_BY_NULL_STATUS = "/api/v1/data/{id}.json?query=\"_review_status\" : null";
    public static String GET_DATA_BY_NULL_SUBMISSION_REVIEW = "/api/v1/data.json?query=\"_review_status\" : null";
    public static String GET_DATA_BY_CREATED_DATE = "/api/v1/data/{id}?date_created__year=2023";
    public static String GET_DATA_BY_MODIFIED_DATE = "/api/v1/data/{id}?date_modified__month=5";
    public static String GET_DATA_BY_LAST_EDIT_DATE = "/api/v1/data/{id}?last_edited__year=2022&last_edited__month=6";
    public static String GET_PUBLIC_DATA = "/api/v1/data/public";
    public static String GET_GEO_JSON_DATA= "/api/v1/data/{id}/{id2}.geojson";

    public static String FILTER_DATA_BY_OWNER = "/api/v1/data?owner="+username+"";

    public static String GET_CHARTS_ACCESSIBLE_BY_USER = "/api/v1/charts";
    public static String GET_CHART_FIELDS = "/api/v1/charts/";
    public static String GET_CHART_FOR_SPECIFIC_FIELD = "/api/v1/charts/{id}?field_name=good_or_bad";
    public static String GET_CHART_DATA_FOR_ALL_FIELDS = "/api/v1/charts/{id}?fields=all";

    public static String CHART_FIELD_GROUPED_BY_ANOTHER_FIELD = "/api/v1/charts/{id}.json?field_name=resp_age&group_by=good_or_bad";
    public static String GET_ALL_EXPORTS = "/api/v1/export";
    public static String GET_FORM_EXPORTS = "/api/v1/export?xform=";
    public static String GET_DATA_EXPORT_IN_CSV = "/api/v1/forms/{id}/export_async?format=csv";
    public static String GET_DATA_EXPORT_IN_XLS = "/api/v1/forms/{id}/export_async?format=xlsx";
    public static String GET_DATA_EXPORT_IN_CSVZIP = "/api/v1/forms/{id}/export_async?format=csvzip";
    public static String GET_DATA_EXPORT_IN_SAV = "/api/v1/forms/{id}/export_async?format=savzip";
    public static String GET_LIST_OF_FORMS = "/api/v1/forms";
    public static String GET_FORM_XML_REPRESENTATION = "/api/v1/forms/{id}/form.xml";
    public static String GET_FORM_JSON_REPRESENTATION = "/api/v1/forms/{id}/form.json";
    public static String GET_XLSFORM_REPRESENTATION = "/api/v1/forms/{id}/form.xls";

    public static String ADD_TAGS_TO_A_FORM = "/api/v1/forms/{id}/labels";
    public static String GET_TAGS = "/api/v1/forms/{id}/labels";
    public static String GET_FORM_WITH_SPECIFIC_TAGS = "/api/v1/forms?tags=";
    public static String GET_ENKETO_URLS = "/api/v1/forms/{id}/enketo";
    public static String GET_SINGLE_SUBMISSION_URL = "/api/v1/forms/{id}/enketo?survey_type=single";
    public static String GET_FORM_CSV_DATA = "/api/v1/forms/{id}.csv";
    public static String GET_FORM_XLS_DATA = "/api/v1/forms/{id}.xlsx";
    public static String GET_FORM_VERSIONS = "/api/v1/forms/{id}/versions";

    public static String FILTER_FORMS_BY_OWNER = "/api/v1/forms?owner="+username+"";

    public static String PAGINATE_LIST_OF_FORMS = "/api/v1/forms.json?page=1&page_size=10";

    public static String GET_FORM_INFORMATION = "/api/v1/forms/";

    public static String REPLACE_A_FORM = "/api/v1/forms/";

    public static String CLONE_A_FORM = "/api/v1/forms/{id}/clone";

    public static String DELETE_CLONED_FORM = "/api/v1/forms/";

    public static String DELETE_A_FORM = "/api/v1/forms/";

    public static String GET_LIST_OF_FORMS_IN_ACCOUNT = "/"+username+"/formList";
    public static String GET_A_SPECIFIC_FORM = "/"+username+"/{id}/formList";
    public static String FILTER_FORM_WITH_ENKETO = "/enketo/{id}/formList";
    public static String FILTER_FORM_WITH_PREVIEW = "/enketo-preview/{id}/formList";

    public static String CREATE_A_PROJECT = "/api/v1/projects";
    public static String GET_LIST_OF_PROJECTS = "/api/v1/projects";
    public static String GET_PROJECTS_BY_OWNER = "/api/v1/projects?owner="+username+"";
    public static String GET_PROJECT_INFORMATION = "/api/v1/projects/";
    public static String UPDATE_A_PROJECT = "/api/v1/projects/";
    public static String SHARE_A_PROJECT = "/api/v1/projects/{id}/share";
    public static String SHARE_MULTIPLE_USERS = "/api/v1/projects/{id}/share";

    public static String SEND_EMAIL_ON_SHARING = "/api/v1/projects/{id}/share";
    public static String REMOVE_A_USER = "/api/v1/projects/{id}/share";
    public static String ASSIGN_A_FORM = "/api/v1/projects/{id}/forms";
    public static String GET_FORMS_IN_PROJECT = "/api/v1/projects/{id}/forms";
    public static String TAG_A_PROJECT = "/api/v1/projects/{id}/labels";
    public static String GET_PROJECT_TAGS = "/api/v1/projects/{id}/labels";
    public static String FILTER_PROJECT_BY_TAGS = "/api/v1/projects?tags=";
    public static String STAR_A_PROJECT = "/api/v1/projects/{id}/star";
    public static String REMOVE_A_STAR = "/api/v1/projects/{id}/star";
    public static String GET_STARRED_PROJECTS = "/api/v1/projects/{id}/star";
    public static String UPLOAD_A_FORM = "/api/v1/projects/{id}/forms";

    public static String DELETE_A_PROJECT = "/api/v1/projects/";
    public static String MAKE_SUBMISSION_REVIEW = "/api/v1/submissionreview.json";
    public static String GET_SUBMISSION_REVIEW = "/api/v1/submissionreview/{id}.json";
    public static String GET_LIST_OF_SUBMISSION_REVIEWS = "/api/v1/submissionreview.json";

    public static String FILTER_REVIEW_BY_INSTANCE = "/api/v1/submissionreview?instance=";
    public static String FILTER_REVIEW_BY_STATUS = "/api/v1/submissionreview?status=1";
    public static String CREATE_WIDGET = "/api/v1/widgets";
    public static String GET_A_WIDGET = "/api/v1/widgets/";
    public static String GET_LIST_OF_WIDGETS = "/api/v1/widgets";
    public static String UPDATE_A_WIDGET = "/api/v1/widgets/";
    public static String PATCH_A_WIDGET = "/api/v1/widgets/";
    public static String GET_WIDGETS_DATA = "/api/v1/widgets/{id}?data=true";
    public static String GET_WIDGET_WITH_VALID_kEY = "/api/v1/widgets?key=";
    public static String FILTER_WIDGET_BY_FORMID = "/api/v1/widgets?xform=";
    public static String FILTER_WIDGET_BY_DATASET = "/api/v1/widgets?dataview=";
    public static String GET_MEDIA_FILES_IN_FORM = "/api/v1/media?xform=";
    public static String PAGINATE_MEDIA_FILES = "/api/v1/media.json?xform={id}&page=1&page_size=10";
    public static String GET_FORM_MEDIA_COUNT = "/api/v1/media/count?xform=";

    public static String UPLOAD_XML_SUBMISSION = "/api/v1/submissions";

    public static String GET_SPECIFC_MEDIA_FILE = "/api/v1/media/{id}.jpeg";

    public static String GET_MEDIA_OF_SPECIFIC_INSTANCE = "/api/v1/media?instance=";

    public static String FILTER_MEDIA_BY_TYPE = "/api/v1/media?type=image/jpg";

    public static String GET_IMAGE_LINK_OF_ATTACHMENT ="/api/v1/media/{id}?filename=";

    public static String GET_ATTACHMENT_DETAILS = "/api/v1/media/";

    public static String GET_LIST_OF_ALL_NOTES = "/api/v1/notes";
    public static String GET_NOTES_IN_SUBMISSION = "/api/v1/notes?instance=";
    public static String ADD_A_NOTE = "/api/v1/notes";

    public static String DELETE_A_NOTE = "/api/v1/notes/";
    public static String MERGE_DATASETS = "/api/v1/merged-datasets";
    public static String GET_MERGED_DATASET = "/api/v1/merged-datasets/";
    public static String GET_ALL_MERGED_DATASETS = "/api/v1/merged-datasets";
    public static String GET_DATA_IN_MERGED_DATASET = "/api/v1/merged-datasets/{id}/data";

    public static String DELETE_A_MERGED_DATASET = "/api/v1/merged-datasets/";
    public static String CREATE_FILTERED_DATASET = "/api/v1/dataviews";
    public static String GET_FILTERED_DATASET = "/api/v1/dataviews/";
    public static String UPDATE_A_DATASET = "/api/v1/dataviews/";
    public static String PATCH_A_DATASET = "/api/v1/dataviews/";
    public static String GET_DATA_FROM_A_DATASET = "/api/v1/dataviews/{id}/data";
    public static String GET_DATA_USING_LIMIT_OPERATORS = "/api/v1/dataviews/{id}/data?start=5";
    public static String GET_DATA_USING_START_LIMIT_OPERATORS = "/api/v1/dataviews/{id}/data?start=2&limit=5";
    public static String COUNT_DATA_IN_DATASET = "/api/v1/dataviews/{id}/data?count=true";
    public static String EXPORT_DATA_IN_DATASET = "/api/v1/dataviews/{id}/export_async?format=xlsx";
    public static String CHARTS_IN_DATASET = "/api/v1/dataviews/{id}/charts";
    public static String CHART_FOR_SPECIFIC_FIELD = "/api/v1/dataviews/{id}/charts.json?field_name=resp_age";
    public static String DELETE_A_FILTERED_DATASET = "/api/v1/dataviews/";

    public static String CREATE_METADATA = "/api/v1/metadata";

    public static String GET_FORM_METADATA = "/api/v1/metadata?xform=";
    public static String GET_SPECIFIC_METADATA = "/api/v1/metadata/";

    public static String DELETE_METADATA = "/api/v1/metadata/";
    public static String GET_SUBMISSION_STATS = "/api/v1/stats/submissions/{id}?group=_submission_time&name=day_of_submission";

    public static String GET_STATS_SUMMARY = "/api/v1/stats/";

    public static String GET_SPECIFIC_STATS = "/api/v1/stats/{id}?method=mean";

    public static String ADD_REST_SERVICE = "/api/v1/restservices";

    public static String LIST_REST_SERVICES = "/api/v1/restservices";

    public static String LIST_SPECIFIC_RESTSERVICE = "/api/v1/restservices/";

    public static String DELETE_A_RESTSERVICE = "/api/v1/restservices/";

    public static String ADD_GOOGLE_SHEET_SYNC = "/api/v1/restservices";

    public static String CREATE_AN_ORGANIZATION = "/api/v1/orgs";

    public static String LIST_ORGANIZATIONS = "/api/v1/orgs";

    public static String ORG_SHARED_WITH_ANOTHER_USER = "/api/v1/orgs?shared_with=onasupport";

    public static String RETRIEVE_ORG_PROFILE = "/api/v1/orgs/";

    public static String UPDATE_ORG_PROFILE = "/api/v1/orgs/";

    public static String ADD_USER_TO_ORG = "/api/v1/orgs/{name}/members";

    public static String LIST_ORG_MEMBERS = "/api/v1/orgs/{name}/members";

    public static String UPDATE_MEMBER_ROLE = "/api/v1/orgs/{name}/members";

    public static String REMOVE_MEMBER_FROM_ORG = "/api/v1/orgs/{name}/members";

    public static String GET_EVENT_MESSAGES = "/api/v1/messaging?target_type=xform&target_id=";

    public static String GET_EVENTS_FOR_SPECIFIC_VERB = "/api/v1/messaging?target_type=xform&target_id={id}&verb=message";

    public static String PAGINATE_EVENTS_FOR_A_VERB = "/api/v1/messaging?target_type=xform&target_id={id}" +
            "&verb=message&page=1&page_size=1";

    public static String GET_MESSAGING_STATS = "/api/v1/messaging?target_type=xform&target_id={id}&group_by=2022";

    public static String GET_USER_PROFILE_INFO = "/api/v1/profiles/"+username+"";

    public static String UPDATE_USER_INFO = "/api/v1/profiles/"+username+"";

    public static String GET_MONTHLY_SUBMISSIONS = "/api/v1/profiles/"+username+"/monthly_submissions";

    public static String GET_LIST_OF_TEAMS = "/api/v1/teams";

    public static String FILTER_TEAM_BY_ORG = "/api/v1/teams?org="+orgUserName+"";

    public static String FILTER_TEAM_BY_ID = "/api/v1/teams/";

    public static String LIST_MEMBERS_OF_A_TEAM = "/api/v1/teams/{id}/members";

    public static String ADD_USER_TO_TEAM = "/api/v1/teams/{id}/members";

    public static String TEAM_PERMISSION_IN_PROJECT = "/api/v1/teams/{id}/share";

    public static String REMOVE_MEMBER_FROM_TEAM = "/api/v1/teams/{id}/members";

    public static String RETRIEVE_USER_PROFILE = "/api/v1/user";

    public static String GET_PROJECTS_STARRED_BY_USER = "/api/v1/user/"+username+"/starred";

    public static String LIST_USERS = "/api/v1/user";

    public static String LIST_USERS_EXCLUDING_ORGS = "/api/v1/users?orgs=false";

    public static String GET_SPECIFIC_USER_INFO = "/api/v1/users/"+username+"";

    public static String SEARCH_FOR_USER_USING_EMAIL = "/api/v1/users?search=support@ona.io";

}
