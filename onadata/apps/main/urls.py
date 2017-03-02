import django

from django.conf import settings
from django.conf.urls import include, url, i18n
from django.contrib.staticfiles import views as staticfiles_views
from django.views.generic import RedirectView

from onadata.apps import sms_support
from onadata.apps.api.viewsets.dataview_viewset import DataViewViewSet
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

admin.autodiscover()

urlpatterns = [
    # change Language
    url(r'^i18n/', include(i18n)),
    url('^api/v1/', include(router.urls)),
    url('^api/v1/dataviews/(?P<pk>[^/]+)/(?P<action>[^/]+).'
        '(?P<format>([a-z]|[0-9])*)$', DataViewViewSet,
        name='dataviews-data'),
    url(r'^api-docs/',
        RedirectView.as_view(url=settings.STATIC_DOC, permanent=True)),
    url(r'^api/$',
        RedirectView.as_view(url=settings.STATIC_DOC, permanent=True)),
    url(r'^api/v1$', RedirectView.as_view(url='/api/v1/', permanent=True)),

    # django default stuff
    url(r'^accounts/', include(registration_patterns)),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # oath2_provider
    url(r'^o/', include('oauth2_provider.urls', namespace='oauth2_provider')),

    # main website views
    url(r'^$', main_views.home),
    url(r'^tutorial/$', main_views.tutorial, name='tutorial'),
    url(r'^about-us/$', main_views.about_us, name='about-us'),
    url(r'^getting_started/$', main_views.getting_started,
        name='getting_started'),
    url(r'^faq/$', main_views.faq, name='faq'),
    url(r'^syntax/$', main_views.syntax, name='syntax'),
    url(r'^privacy/$', main_views.privacy, name='privacy'),
    url(r'^tos/$', main_views.tos, name='tos'),
    url(r'^resources/$', main_views.resources, name='resources'),
    url(r'^forms/$', main_views.form_gallery, name='forms_list'),
    url(r'^forms/(?P<uuid>[^/]+)$', main_views.show, name='form-show'),
    url(r'^people/$', main_views.members_list, name='members-list'),
    url(r'^xls2xform/$', main_views.xls2xform),
    url(r'^support/$', main_views.support, name='support'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/stats$',
        viewer_views.charts, name='form-stats'),
    url(r'^login_redirect/$', main_views.login_redirect),
    url(r'^attachment/$', viewer_views.attachment_url),
    url(r'^attachment/(?P<size>[^/]+)$', viewer_views.attachment_url),
    url(r'^jsi18n/$', django.views.i18n.javascript_catalog,
        {'packages': ('main', 'viewer',)}, name='javascript-catalog'),
    url(r'^typeahead_usernames', main_views.username_list,
        name='username_list'),
    url(r'^(?P<username>[^/]+)/$', main_views.profile, name='user_profile'),
    url(r'^(?P<username>[^/]+)/profile$', main_views.public_profile,
        name='public_profile'),
    url(r'^(?P<username>[^/]+)/settings', main_views.profile_settings,
        name='profile-settings'),
    url(r'^(?P<username>[^/]+)/cloneform$', main_views.clone_xlsform),
    url(r'^(?P<username>[^/]+)/activity$', main_views.activity,
        name='activity'),
    url(r'^(?P<username>[^/]+)/activity/api$', main_views.activity_api,
        name='activity-api'),
    url(r'^activity/fields$', main_views.activity_fields,
        name='activity-fields'),
    url(r'^(?P<username>[^/]+)/api-token$', main_views.api_token,
        name='api-token'),

    # form specific
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)$', main_views.show,
        name='form-show'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/qrcode$',
        main_views.qrcode, name='get_qrcode'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/api$',
        main_views.api, name='mongo_view_api'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/public_api$',
        main_views.public_api, name='public_api'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/delete_data$',
        main_views.delete_data, name='delete_data'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/edit$',
        main_views.edit, name='xform-edit'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/perms$',
        main_views.set_perm, name='set-xform-permissions'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/photos',
        main_views.form_photos, name='form-photos'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/doc/(?P<data_id>\d+)'
        '', main_views.download_metadata),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/delete-doc/(?P<data_'
        'id>\d+)', main_views.delete_metadata),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/formid-media/(?P<dat'
        'a_id>\d+)', main_views.download_media_data),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/addservice$',
        restservice_views.add_service, name='add_restservice'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/delservice$',
        restservice_views.delete_service,
        name='delete_restservice'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/update$',
        main_views.update_xform, name='update-xform'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/preview$',
        main_views.enketo_preview, name='enketo-preview'),

    # briefcase api urls
    url(r'^(?P<username>\w+)/view/submissionList$',
        BriefcaseViewset.as_view({'get': 'list', 'head': 'list'}),
        name='view-submission-list'),
    url(r'^(?P<username>\w+)/view/downloadSubmission$',
        BriefcaseViewset.as_view({'get': 'retrieve', 'head': 'retrieve'}),
        name='view-download-submission'),
    url(r'^(?P<username>\w+)/formUpload$',
        BriefcaseViewset.as_view({'post': 'create', 'head': 'create'}),
        name='form-upload'),
    url(r'^(?P<username>\w+)/upload$',
        BriefcaseViewset.as_view({'post': 'create', 'head': 'create'}),
        name='upload'),

    # exporting stuff
    url(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/data\.csv$',
        viewer_views.data_export, name='csv_export',
        kwargs={'export_type': 'csv'}),
    url(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/data\.xls',
        viewer_views.data_export, name='xls_export',
        kwargs={'export_type': 'xls'}),
    url(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/data\.csv.zip',
        viewer_views.data_export, name='csv_zip_export',
        kwargs={'export_type': 'csv_zip'}),
    url(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/data\.sav.zip',
        viewer_views.data_export, name='sav_zip_export',
        kwargs={'export_type': 'sav_zip'}),
    url(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/data\.kml$',
        viewer_views.kml_export, name='kml-export'),
    url(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/data\.zip',
        viewer_views.zip_export),
    url(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/gdocs$',
        viewer_views.google_xls_export),
    url(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/map_embed',
        viewer_views.map_embed_view),
    url(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/map',
        viewer_views.map_view, name='map-view'),
    url(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/instance',
        viewer_views.instance, name='submission-instance'),
    url(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/enter-data',
        logger_views.enter_data, name='enter_data'),
    url(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/add-submission-with',
        viewer_views.add_submission_with,
        name='add_submission_with'),
    url(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/thank_you_submission',
        viewer_views.thank_you_submission,
        name='thank_you_submission'),
    url(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/edit-data/(?P<data_id>'
        '\d+)$', logger_views.edit_data, name='edit_data'),
    url(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/view-data',
        viewer_views.data_view, name='data-view'),
    url(r'^(?P<username>\w+)/exports/(?P<id_string>[^/]+)/(?P<export_type>\w+)'
        '/new$', viewer_views.create_export, name='new-export'),
    url(r'^(?P<username>\w+)/exports/(?P<id_string>[^/]+)/(?P<export_type>\w+)'
        '/delete$', viewer_views.delete_export, name='delete-export'),
    url(r'^(?P<username>\w+)/exports/(?P<id_string>[^/]+)/(?P<export_type>\w+)'
        '/progress$', viewer_views.export_progress, name='export-progress'),
    url(r'^(?P<username>\w+)/exports/(?P<id_string>[^/]+)/(?P<export_type>\w+)'
        '/$', viewer_views.export_list, name='export-list'),
    url(r'^(?P<username>\w+)/exports/(?P<id_string>[^/]+)/(?P<export_type>\w+)'
        '/(?P<filename>[^/]+)$',
        viewer_views.export_download, name='export-download'),

    # odk data urls
    url(r'^submission$',
        XFormSubmissionViewSet.as_view({'post': 'create', 'head': 'create'}),
        name='submissions'),
    url(r'^formList$',
        XFormListViewSet.as_view({'get': 'list'}), name='form-list'),
    url(r'^(?P<username>\w+)/formList$',
        XFormListViewSet.as_view({'get': 'list'}), name='form-list'),
    url(r'^preview/(?P<username>\w+)/formList$',
        PreviewXFormListViewSet.as_view({'get': 'list'}), name='form-list'),
    url(r'^(?P<username>\w+)/xformsManifest/(?P<pk>[\d+^/]+)$',
        XFormListViewSet.as_view({'get': 'manifest'}), name='manifest-url'),
    url(r'^xformsManifest/(?P<pk>[\d+^/]+)$',
        XFormListViewSet.as_view({'get': 'manifest'}), name='manifest-url'),
    url(r'^(?P<username>\w+)/xformsMedia/(?P<pk>[\d+^/]+)'
        '/(?P<metadata>[\d+^/.]+)$',
        XFormListViewSet.as_view({'get': 'media'}), name='xform-media'),
    url(r'^(?P<username>\w+)/xformsMedia/(?P<pk>[\d+^/]+)'
        '/(?P<metadata>[\d+^/.]+)\.(?P<format>([a-z]|[0-9])*)$',
        XFormListViewSet.as_view({'get': 'media'}), name='xform-media'),
    url(r'^xformsMedia/(?P<pk>[\d+^/]+)/(?P<metadata>[\d+^/.]+)$',
        XFormListViewSet.as_view({'get': 'media'}), name='xform-media'),
    url(r'^xformsMedia/(?P<pk>[\d+^/]+)/(?P<metadata>[\d+^/.]+)\.'
        '(?P<format>([a-z]|[0-9])*)$',
        XFormListViewSet.as_view({'get': 'media'}), name='xform-media'),
    url(r'^(?P<username>\w+)/submission$',
        XFormSubmissionViewSet.as_view({'post': 'create', 'head': 'create'}),
        name='submissions'),
    url(r'^(?P<username>\w+)/bulk-submission$',
        logger_views.bulksubmission),
    url(r'^(?P<username>\w+)/bulk-submission-form$',
        logger_views.bulksubmission_form),
    url(r'^(?P<username>\w+)/forms/(?P<pk>[\d+^/]+)/form\.xml$',
        XFormListViewSet.as_view({'get': 'retrieve'}),
        name='download_xform'),
    url(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/form\.xml$',
        logger_views.download_xform, name='download_xform'),
    url(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/form\.xls$',
        logger_views.download_xlsform,
        name='download_xlsform'),
    url(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/form\.json',
        logger_views.download_jsonform,
        name='download_jsonform'),
    url(r'^(?P<username>\w+)/delete/(?P<id_string>[^/]+)/$',
        logger_views.delete_xform, name='delete-xform'),
    url(r'^(?P<username>\w+)/(?P<id_string>[^/]+)/toggle_downloadable/$',
        logger_views.toggle_downloadable),

    # SMS support
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/sms_submission/(?P<s'
        'ervice>[a-z]+)/?$',
        sms_support.providers.import_submission_for_form,
        name='sms_submission_form_api'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/sms_submission$',
        sms_support_views.import_submission_for_form,
        name='sms_submission_form'),
    url(r'^(?P<username>[^/]+)/sms_submission/(?P<service>[a-z]+)/?$',
        sms_support.providers.import_submission,
        name='sms_submission_api'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/sms_multiple_submiss'
        'ions$',
        sms_support_views.import_multiple_submissions_for_form,
        name='sms_submissions_form'),
    url(r'^(?P<username>[^/]+)/sms_multiple_submissions$',
        sms_support_views.import_multiple_submissions,
        name='sms_submissions'),
    url(r'^(?P<username>[^/]+)/sms_submission$',
        sms_support_views.import_submission, name='sms_submission'),

    # Stats tables
    url(r'^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/tables',
        viewer_views.stats_tables, name='stats-tables'),

    # static media
    url(r'^media/(?P<path>.*)$', django.views.static.serve,
        {'document_root': settings.MEDIA_ROOT}),
    url(r'^favicon\.ico',
        RedirectView.as_view(url='/static/images/favicon.ico',
                             permanent=True)),
    url(r'^static/(?P<path>.*)$', staticfiles_views.serve)
]

custom_urls = getattr(settings, 'CUSTOM_MAIN_URLS', None)

if custom_urls:
    for url_module in custom_urls:
        urlpatterns.append(url(r'^', include(url_module)))

if settings.DEBUG and 'debug_toolbar' in settings.INSTALLED_APPS:
    try:
        import debug_toolbar
    except ImportError:
        pass
    else:
        urlpatterns += [
            url(r'^__debug__/', include(debug_toolbar.urls)),
        ]
