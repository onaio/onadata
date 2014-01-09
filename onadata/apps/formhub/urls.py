from django.conf.urls import patterns, include, url
from django.conf import settings
from django.views.generic import RedirectView

from onadata.apps.api.urls import router

# Uncomment the next two lines to enable the admin:
from django.contrib import admin

admin.autodiscover()

urlpatterns = patterns(
    '',
    # change Language
    (r'^i18n/', include('django.conf.urls.i18n')),
    url('^api/v1/', include(router.urls)),
    url(r'^api-docs/', RedirectView.as_view(url='/api/v1/')),
    url(r'^api/', RedirectView.as_view(url='/api/v1/')),
    url(r'^api/v1', RedirectView.as_view(url='/api/v1/')),

    # django default stuff
    url(r'^accounts/', include('onadata.apps.main.registration_urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # oath2_provider
    url(r'^o/', include('oauth2_provider.urls', namespace='oauth2_provider')),

    # google urls
    url(r'^gauthtest/$',
        'onadata.apps.main.google_export.google_oauth2_request',
        name='google-auth'),
    url(r'^gwelcome/$',
        'onadata.apps.main.google_export.google_auth_return',
        name='google-auth-welcome'),

    # main website views
    url(r'^$', 'onadata.apps.main.views.home'),
    url(r'^tutorial/$', 'onadata.apps.main.views.tutorial', name='tutorial'),
    url(r'^about-us/$', 'onadata.apps.main.views.about_us', name='about-us'),
    url(r'^getting_started/$', 'onadata.apps.main.views.getting_started',
        name='getting_started'),
    url(r'^faq/$', 'onadata.apps.main.views.faq', name='faq'),
    url(r'^syntax/$', 'onadata.apps.main.views.syntax', name='syntax'),
    url(r'^resources/$', 'onadata.apps.main.views.resources', name='resources'),
    url(r'^forms/$', 'onadata.apps.main.views.form_gallery', name='forms_list'),
    url(r'^forms/(?P<uuid>[^/]+)$', 'onadata.apps.main.views.show'),
    url(r'^people/$', 'onadata.apps.main.views.members_list'),
    url(r'^xls2xform/$', 'onadata.apps.main.views.xls2xform'),
    url(r'^support/$', 'onadata.apps.main.views.support'),
    url(r'^stats/$', 'onadata.apps.stats.views.stats', name='form-stats'),
    url(r'^stats/(?P<username>[^/]+)/(?P<id_string>[^/]+)$',
        'onadata.apps.stats.views.stats', name='form-stats'),
    url(r'^login_redirect/$', 'onadata.apps.main.views.login_redirect'),
    url(r"^attachment/$", 'onadata.apps.odk_viewer.views.attachment_url'),
    url(r"^attachment/(?P<size>[^/]+)$",
        'onadata.apps.odk_viewer.views.attachment_url'),
    url(r'^jsi18n/$', 'django.views.i18n.javascript_catalog',
        {'packages': ('main', 'odk_viewer',)}),
    url(r'^typeahead_usernames', 'onadata.apps.main.views.username_list',
        name='username_list'),
    url(r'^(?P<username>[^/]+)/$',
        'onadata.apps.main.views.profile', name='user_profile'),
    url(r'^(?P<username>[^/]+)/profile$', 'onadata.apps.main.views.public_profile',
        name='public_profile'),
    url(r'^(?P<username>[^/]+)/settings', 'onadata.apps.main.views.profile_settings'),
    url(r'^(?P<username>[^/]+)/cloneform$', 'onadata.apps.main.views.clone_xlsform'),
    url(r'^(?P<username>[^/]+)/activity$', 'onadata.apps.main.views.activity'),
    url(r'^(?P<username>[^/]+)/activity/api$', 'onadata.apps.main.views.activity_api'),
    url(r'^activity/fields$', 'onadata.apps.main.views.activity_fields'),
    url(r'^(?P<username>[^/]+)/api-token$', 'onadata.apps.main.views.api_token'),

    # form specific
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)$',
        'onadata.apps.main.views.show'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/qrcode$',
        'onadata.apps.main.views.qrcode', name='get_qrcode'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/api$',
        'onadata.apps.main.views.api', name='mongo_view_api'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/public_api$',
        'onadata.apps.main.views.public_api', name='public_api'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/delete_data$',
        'onadata.apps.main.views.delete_data', name='delete_data'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/edit$',
        'onadata.apps.main.views.edit'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/perms$',
        'onadata.apps.main.views.set_perm'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/bamboo$',
        'onadata.apps.main.views.link_to_bamboo'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/photos',
        'onadata.apps.main.views.form_photos'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/doc/(?P<data_id>\d+)'
        '', 'onadata.apps.main.views.download_metadata'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/delete-doc/(?P<data_'
        'id>\d+)', 'onadata.apps.main.views.delete_metadata'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/formid-media/(?P<dat'
        'a_id>\d+)', 'onadata.apps.main.views.download_media_data'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/submission/(?P<uuid>'
        '[^/]+)$', 'onadata.apps.main.views.show_submission'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/addservice$',
        'onadata.apps.restservice.views.add_service', name="add_restservice"),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/delservice$',
        'onadata.apps.restservice.views.delete_service', name="delete_restservice"),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/update$',
        'onadata.apps.main.views.update_xform'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/preview$',
        'onadata.apps.main.views.enketo_preview'),

    # briefcase api urls
    url(r"^(?P<username>\w+)/view/submissionList$",
        'onadata.apps.odk_logger.views.view_submission_list'),
    url(r"^(?P<username>\w+)/view/downloadSubmission$",
        'onadata.apps.odk_logger.views.view_download_submission'),
    url(r"^(?P<username>\w+)/formUpload$",
        'onadata.apps.odk_logger.views.form_upload'),
    url(r"^(?P<username>\w+)/upload$",
        'onadata.apps.odk_logger.views.form_upload'),

    # stats
    url(r"^stats/submissions/$", 'onadata.apps.stats.views.submissions'),

    # exporting stuff
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/data\.csv$",
        'onadata.apps.odk_viewer.views.data_export', name='csv_export',
        kwargs={'export_type': 'csv'}),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/data\.xls",
        'onadata.apps.odk_viewer.views.data_export', name='xls_export',
        kwargs={'export_type': 'xls'}),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/data\.csv.zip",
        'onadata.apps.odk_viewer.views.data_export', name='csv_zip_export',
        kwargs={'export_type': 'csv_zip'}),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/data\.sav.zip",
        'onadata.apps.odk_viewer.views.data_export', name='sav_zip_export',
        kwargs={'export_type': 'sav_zip'}),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/data\.kml$",
        'onadata.apps.odk_viewer.views.kml_export'),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/data\.zip",
        'onadata.apps.odk_viewer.views.zip_export'),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/gdocs$",
        'onadata.apps.odk_viewer.views.google_xls_export'),
    url(r"^odk_viewer/survey/(?P<instance_id>\d+)/$",
        'onadata.apps.odk_viewer.views.survey_responses'),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/map_embed",
        'onadata.apps.odk_viewer.views.map_embed_view'),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/map",
        'onadata.apps.odk_viewer.views.map_view'),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/instance",
        'onadata.apps.odk_viewer.views.instance'),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/enter-data",
        'onadata.apps.odk_logger.views.enter_data', name='enter_data'),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/add-submission-with",
        'onadata.apps.odk_viewer.views.add_submission_with',
        name='add_submission_with'),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/thank_you_submission",
        'onadata.apps.odk_viewer.views.thank_you_submission',
        name='thank_you_submission'),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/edit-data/(?P<data_id>"
        "\d+)$", 'onadata.apps.odk_logger.views.edit_data', name='edit_data'),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/view-data",
        'onadata.apps.odk_viewer.views.data_view'),
    url(r"^(?P<username>\w+)/exports/(?P<id_string>[^/]+)/(?P<export_type>\w+)"
        "/new$", 'onadata.apps.odk_viewer.views.create_export'),
    url(r"^(?P<username>\w+)/exports/(?P<id_string>[^/]+)/(?P<export_type>\w+)"
        "/delete$", 'onadata.apps.odk_viewer.views.delete_export'),
    url(r"^(?P<username>\w+)/exports/(?P<id_string>[^/]+)/(?P<export_type>\w+)"
        "/progress$", 'onadata.apps.odk_viewer.views.export_progress'),
    url(r"^(?P<username>\w+)/exports/(?P<id_string>[^/]+)/(?P<export_type>\w+)"
        "/$", 'onadata.apps.odk_viewer.views.export_list'),
    url(r"^(?P<username>\w+)/exports/(?P<id_string>[^/]+)/(?P<export_type>\w+)"
        "/(?P<filename>[^/]+)$", 'onadata.apps.odk_viewer.views.export_download'),

    # odk data urls
    url(r"^submission$", 'onadata.apps.odk_logger.views.submission'),
    url(r"^(?P<username>\w+)/formList$", 'onadata.apps.odk_logger.views.formList'),
    url(r"^(?P<username>\w+)/xformsManifest/(?P<id_string>[^/]+)$",
        'onadata.apps.odk_logger.views.xformsManifest'),
    url(r"^(?P<username>\w+)/submission$", 'onadata.apps.odk_logger.views.submission'),
    url(r"^(?P<username>\w+)/bulk-submission$",
        'onadata.apps.odk_logger.views.bulksubmission'),
    url(r"^(?P<username>\w+)/bulk-submission-form$",
        'onadata.apps.odk_logger.views.bulksubmission_form'),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/form\.xml$",
        'onadata.apps.odk_logger.views.download_xform', name="download_xform"),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/form\.xls$",
        'onadata.apps.odk_logger.views.download_xlsform', name="download_xlsform"),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/form\.json",
        'onadata.apps.odk_logger.views.download_jsonform', name="download_jsonform"),
    url(r"^(?P<username>\w+)/delete/(?P<id_string>[^/]+)/$",
        'onadata.apps.odk_logger.views.delete_xform'),
    url(r"^(?P<username>\w+)/(?P<id_string>[^/]+)/toggle_downloadable/$",
        'onadata.apps.odk_logger.views.toggle_downloadable'),

    # SMS support
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/sms_submission/(?P<s'
        'ervice>[a-z]+)/?$',
        'onadata.apps.sms_support.providers.import_submission_for_form',
        name='sms_submission_form_api'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/sms_submission$',
        'onadata.apps.sms_support.views.import_submission_for_form',
        name='sms_submission_form'),
    url(r"^(?P<username>[^/]+)/sms_submission/(?P<service>[a-z]+)/?$",
        'onadata.apps.sms_support.providers.import_submission',
        name='sms_submission_api'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/sms_multiple_submiss'
        'ions$', 'onadata.apps.sms_support.views.import_multiple_submissions_for_form',
        name='sms_submissions_form'),
    url(r"^(?P<username>[^/]+)/sms_multiple_submissions$",
        'onadata.apps.sms_support.views.import_multiple_submissions',
        name='sms_submissions'),
    url(r"^(?P<username>[^/]+)/sms_submission$",
        'onadata.apps.sms_support.views.import_submission',
        name='sms_submission'),

    # Charts
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/chart/(?P<field_name>[^/]+)$",
        'onadata.apps.odk_viewer.views.chart'),

    # Ziggy
    url(r"^(?P<username>[^/]+)/form-submissions$",
        'onadata.apps.odk_logger.views.ziggy_submissions'),

    # static media
    url(r'^media/(?P<path>.*)$', 'django.views.static.serve',
        {'document_root': settings.MEDIA_ROOT}),
    url(r'^favicon\.ico',
        RedirectView.as_view(url='/static/images/favicon.ico')))

urlpatterns += patterns('django.contrib.staticfiles.views',
                        url(r'^static/(?P<path>.*)$', 'serve'))
