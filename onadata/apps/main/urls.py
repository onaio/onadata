import sys

import django

from django.conf import settings
from django.conf.urls import include, url, i18n
from django.contrib.staticfiles import views as staticfiles_views
from django.urls import re_path, path
from django.views.generic import RedirectView

from onadata.apps import sms_support
from onadata.apps.api.urls import router
from onadata.apps.api.urls import XFormListViewSet
from onadata.apps.api.viewsets.xform_list_viewset import (
    PreviewXFormListViewSet
)
from onadata.apps.api.urls import XFormSubmissionViewSet
from onadata.apps.api.urls import BriefcaseViewset
from onadata.apps.logger import views as logger_views
from onadata.apps.main import views as main_views
from onadata.apps.main.registration_urls import (
    urlpatterns as registration_patterns
)
from onadata.apps.restservice import views as restservice_views
from onadata.apps.sms_support import views as sms_support_views
from onadata.apps.viewer import views as viewer_views

# enable the admin:
from django.contrib import admin

TESTING = len(sys.argv) > 1 and sys.argv[1] == 'test'

admin.autodiscover()

urlpatterns = [
    # change Language
    re_path(r'^i18n/', include(i18n)),
    url('^api/v1/', include(router.urls)),
    re_path(r'^api-docs/',
        RedirectView.as_view(url=settings.STATIC_DOC, permanent=True)),
    re_path(r'^api/$',
        RedirectView.as_view(url=settings.STATIC_DOC, permanent=True)),
    re_path(r'^api/v1$', RedirectView.as_view(url='/api/v1/', permanent=True)),

    # django default stuff
    re_path(r'^accounts/', include(registration_patterns)),
    re_path(r'^admin/', admin.site.urls),
    re_path(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # oath2_provider
    re_path(r'^o/authorize/$', main_views.OnaAuthorizationView.as_view(),
        name="oauth2_provider_authorize"),
    re_path(r'^o/', include('oauth2_provider.urls', namespace='oauth2_provider')),

    # main website views
    re_path(r'^$', main_views.home),
    re_path(r'^tutorial/$', main_views.tutorial, name='tutorial'),
    re_path(r'^about-us/$', main_views.about_us, name='about-us'),
    re_path(r'^getting_started/$', main_views.getting_started,
        name='getting_started'),
    re_path(r'^faq/$', main_views.faq, name='faq'),
    re_path(r'^syntax/$', main_views.syntax, name='syntax'),
    re_path(r'^privacy/$', main_views.privacy, name='privacy'),
    re_path(r'^tos/$', main_views.tos, name='tos'),
    re_path(r'^resources/$', main_views.resources, name='resources'),
    re_path(r'^forms/$', main_views.form_gallery, name='forms_list'),
    re_path(r'^forms/(?P<uuid>[^/]+)$', main_views.show, name='form-show'),
    re_path(r'^people/$', main_views.members_list, name='members-list'),
    re_path(r'^xls2xform/$', main_views.xls2xform),
    re_path(r'^support/$', main_views.support, name='support'),
    re_path(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/stats$',
        viewer_views.charts, name='form-stats'),
    re_path(r'^login_redirect/$', main_views.login_redirect),
    re_path(r'^attachment/$', viewer_views.attachment_url, name='attachment_url'),
    re_path(r'^attachment/(?P<size>[^/]+)$', viewer_views.attachment_url,
        name='attachment_url'),
    re_path(r'^jsi18n/$',
        django.views.i18n.JavaScriptCatalog.as_view(packages=['onadata.apps.main', 'onadata.apps.viewer']),
        name='javascript-catalog'),
    re_path(r'^typeahead_usernames', main_views.username_list,
        name='username_list'),
    re_path(r'^(?P<username>[^/]+)/$', main_views.profile, name='user_profile'),
    re_path(r'^(?P<username>[^/]+)/profile$', main_views.public_profile,
        name='public_profile'),
    re_path(r'^(?P<username>[^/]+)/settings', main_views.profile_settings,
        name='profile-settings'),
    re_path(r'^(?P<username>[^/]+)/cloneform$', main_views.clone_xlsform,
        name='clone-xlsform'),
    re_path(r'^(?P<username>[^/]+)/activity$', main_views.activity,
        name='activity'),
    re_path(r'^(?P<username>[^/]+)/activity/api$', main_views.activity_api,
        name='activity-api'),
    re_path(r'^activity/fields$', main_views.activity_fields,
        name='activity-fields'),
    re_path(r'^(?P<username>[^/]+)/api-token$', main_views.api_token,
        name='api-token'),

    # form specific
    re_path(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)$', main_views.show,
        name='form-show'),
    re_path(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/qrcode$',
        main_views.qrcode, name='get_qrcode'),
    re_path(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/api$',
        main_views.api, name='mongo_view_api'),
    re_path(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/public_api$',
        main_views.public_api, name='public_api'),
    re_path(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/delete_data$',
        main_views.delete_data, name='delete_data'),
    re_path(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/edit$',
        main_views.edit, name='xform-edit'),
    re_path(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/perms$',
        main_views.set_perm, name='set-xform-permissions'),
    re_path(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/photos',
        main_views.form_photos, name='form-photos'),
    re_path(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/doc/(?P<data_id>\d+)'
        '', main_views.download_metadata, name='download-metadata'),
    re_path(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/delete-doc/(?P<data_'
        'id>\d+)', main_views.delete_metadata, name='delete-metadata'),
    re_path(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/formid-media/(?P<dat'
        'a_id>\d+)', main_views.download_media_data,
        name='download-media-data'),
    re_path(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/addservice$',
        restservice_views.add_service, name='add_restservice'),
    re_path(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/delservice$',
        restservice_views.delete_service,
        name='delete_restservice'),
    re_path(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/update$',
        main_views.update_xform, name='update-xform'),
    re_path(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/preview$',
        main_views.enketo_preview, name='enketo-preview'),

    # briefcase api urls
    re_path(r'^(?P<username>\w+)/view/submissionList$',
        BriefcaseViewset.as_view({'get': 'list', 'head': 'list'}),
        name='view-submission-list'),
    re_path(r'^(?P<username>\w+)/view/downloadSubmission$',
        BriefcaseViewset.as_view({'get': 'retrieve', 'head': 'retrieve'}),
        name='view-download-submission'),
    re_path(r'^(?P<username>\w+)/formUpload$',
        BriefcaseViewset.as_view({'post': 'create', 'head': 'create'}),
        name='form-upload'),
    re_path(r'^(?P<username>\w+)/upload$',
        BriefcaseViewset.as_view({'post': 'create', 'head': 'create'}),
        name='upload'),

    # exporting stuff
    re_path(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/data\.csv$',
        viewer_views.data_export, name='csv_export',
        kwargs={'export_type': 'csv'}),
    re_path(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/data\.xls',
        viewer_views.data_export, name='xls_export',
        kwargs={'export_type': 'xls'}),
    re_path(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/data\.csv.zip',
        viewer_views.data_export, name='csv_zip_export',
        kwargs={'export_type': 'csv_zip'}),
    re_path(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/data\.sav.zip',
        viewer_views.data_export, name='sav_zip_export',
        kwargs={'export_type': 'sav_zip'}),
    re_path(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/data\.kml$',
        viewer_views.kml_export, name='kml-export'),
    re_path(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/data\.zip',
        viewer_views.zip_export),
    re_path(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/gdocs$',
        viewer_views.google_xls_export),
    re_path(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/map_embed',
        viewer_views.map_embed_view),
    re_path(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/map',
        viewer_views.map_view, name='map-view'),
    re_path(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/instance',
        viewer_views.instance, name='submission-instance'),
    re_path(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/enter-data',
        logger_views.enter_data, name='enter_data'),
    re_path(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/add-submission-with',
        viewer_views.add_submission_with,
        name='add_submission_with'),
    re_path(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/thank_you_submission',
        viewer_views.thank_you_submission,
        name='thank_you_submission'),
    re_path(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/edit-data/(?P<data_id>'
        '\d+)$', logger_views.edit_data, name='edit_data'),
    re_path(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/view-data',
        viewer_views.data_view, name='data-view'),
    re_path(r'^(?P<username>\w+)/exports/(?P<id_string>[^/]+)/(?P<export_type>\w+)'
        '/new$', viewer_views.create_export, name='new-export'),
    re_path(r'^(?P<username>\w+)/exports/(?P<id_string>[^/]+)/(?P<export_type>\w+)'
        '/delete$', viewer_views.delete_export, name='delete-export'),
    re_path(r'^(?P<username>\w+)/exports/(?P<id_string>[^/]+)/(?P<export_type>\w+)'
        '/progress$', viewer_views.export_progress, name='export-progress'),
    re_path(r'^(?P<username>\w+)/exports/(?P<id_string>[^/]+)/(?P<export_type>\w+)'
        '/$', viewer_views.export_list, name='export-list'),
    re_path(r'^(?P<username>\w+)/exports/(?P<id_string>[^/]+)/(?P<export_type>\w+)'
        '/(?P<filename>[^/]+)$',
        viewer_views.export_download, name='export-download'),

    # odk data urls
    re_path(r'^submission$',
        XFormSubmissionViewSet.as_view({'post': 'create', 'head': 'create'}),
        name='submissions'),
    re_path(r'^formList$',
        XFormListViewSet.as_view({'get': 'list', 'head': 'list'}),
        name='form-list'),
    re_path(r'^(?P<username>\w+)/formList$',
        XFormListViewSet.as_view({'get': 'list', 'head': 'list'}),
        name='form-list'),
    re_path(r'^(?P<username>\w+)/(?P<xform_pk>\d+)/formList$',
        XFormListViewSet.as_view({'get': 'list', 'head': 'list'}),
        name='form-list'),
    re_path(r'^preview/(?P<username>\w+)/(?P<xform_pk>\d+)/formList$',
        PreviewXFormListViewSet.as_view({'get': 'list', 'head': 'list'}),
        name='form-list'),
    re_path(r'^preview/(?P<username>\w+)/formList$',
        PreviewXFormListViewSet.as_view({'get': 'list', 'head': 'list'}),
        name='form-list'),
    re_path(r'^(?P<username>\w+)/xformsManifest/(?P<pk>[\d+^/]+)$',
        XFormListViewSet.as_view({'get': 'manifest', 'head': 'manifest'}),
        name='manifest-url'),
    re_path(r'^xformsManifest/(?P<pk>[\d+^/]+)$',
        XFormListViewSet.as_view({'get': 'manifest', 'head': 'manifest'}),
        name='manifest-url'),
    re_path(r'^(?P<username>\w+)/xformsMedia/(?P<pk>[\d+^/]+)'
        '/(?P<metadata>[\d+^/.]+)$',
        XFormListViewSet.as_view({'get': 'media', 'head': 'media'}),
        name='xform-media'),
    re_path(r'^(?P<username>\w+)/xformsMedia/(?P<pk>[\d+^/]+)'
        '/(?P<metadata>[\d+^/.]+)\.(?P<format>([a-z]|[0-9])*)$',
        XFormListViewSet.as_view({'get': 'media', 'head': 'media'}),
        name='xform-media'),
    re_path(r'^xformsMedia/(?P<pk>[\d+^/]+)/(?P<metadata>[\d+^/.]+)$',
        XFormListViewSet.as_view({'get': 'media', 'head': 'media'}),
        name='xform-media'),
    re_path(r'^xformsMedia/(?P<pk>[\d+^/]+)/(?P<metadata>[\d+^/.]+)\.'
        '(?P<format>([a-z]|[0-9])*)$',
        XFormListViewSet.as_view({'get': 'media', 'head': 'media'}),
        name='xform-media'),
    re_path(r'^(?P<username>\w+)/submission$',
        XFormSubmissionViewSet.as_view({'post': 'create', 'head': 'create'}),
        name='submissions'),
    re_path(r'^(?P<username>\w+)/(?P<xform_pk>\d+)/submission$',
        XFormSubmissionViewSet.as_view({'post': 'create', 'head': 'create'}),
        name='submissions'),
    re_path(r'^(?P<username>\w+)/bulk-submission$',
        logger_views.bulksubmission),
    re_path(r'^(?P<username>\w+)/bulk-submission-form$',
        logger_views.bulksubmission_form),
    re_path(r'^(?P<username>\w+)/forms/(?P<pk>[\d+^/]+)/form\.xml$',
        XFormListViewSet.as_view({'get': 'retrieve', 'head': 'retrieve'}),
        name='download_xform'),
    re_path(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/form\.xml$',
        logger_views.download_xform, name='download_xform'),
    re_path(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/form\.xls$',
        logger_views.download_xlsform,
        name='download_xlsform'),
    re_path(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/form\.json',
        logger_views.download_jsonform,
        name='download_jsonform'),
    re_path(r'^(?P<username>\w+)/delete/(?P<id_string>[^/]+)/$',
        logger_views.delete_xform, name='delete-xform'),
    re_path(r'^(?P<username>\w+)/(?P<id_string>[^/]+)/toggle_downloadable/$',
        logger_views.toggle_downloadable, name='toggle-downloadable'),

    # SMS support
    re_path(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/sms_submission/(?P<s'
        'ervice>[a-z]+)/?$',
        sms_support.providers.import_submission_for_form,
        name='sms_submission_form_api'),
    re_path(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/sms_submission$',
        sms_support_views.import_submission_for_form,
        name='sms_submission_form'),
    re_path(r'^(?P<username>[^/]+)/sms_submission/(?P<service>[a-z]+)/?$',
        sms_support.providers.import_submission,
        name='sms_submission_api'),
    re_path(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/sms_multiple_submiss'
        'ions$',
        sms_support_views.import_multiple_submissions_for_form,
        name='sms_submissions_form'),
    re_path(r'^(?P<username>[^/]+)/sms_multiple_submissions$',
        sms_support_views.import_multiple_submissions,
        name='sms_submissions'),
    re_path(r'^(?P<username>[^/]+)/sms_submission$',
        sms_support_views.import_submission, name='sms_submission'),

    # Stats tables
    re_path(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/tables',
        viewer_views.stats_tables, name='stats-tables'),

    # static media
    re_path(r'^media/(?P<path>.*)$', django.views.static.serve,
        {'document_root': settings.MEDIA_ROOT}),
    re_path(r'^favicon\.ico',
        RedirectView.as_view(url='/static/images/favicon.ico',
                             permanent=True)),
    re_path(r'^static/(?P<path>.*)$', staticfiles_views.serve)
]

# messaging urls
urlpatterns.append(url('^', include('onadata.apps.messaging.urls')))

CUSTOM_URLS = getattr(settings, 'CUSTOM_MAIN_URLS', None)

if CUSTOM_URLS:
    for url_module in CUSTOM_URLS:
        urlpatterns.append(re_path(r'^', include(url_module)))

if (settings.DEBUG or TESTING) and 'debug_toolbar' in settings.INSTALLED_APPS:
    try:
        import debug_toolbar
    except ImportError:
        pass
    else:
        urlpatterns += [
            re_path(r'^__debug__/', include(debug_toolbar.urls)),
        ]
