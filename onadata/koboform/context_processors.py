from onadata import koboform


def koboform_integration(request):
    return {
        u'koboform_url': koboform.url,
        u'koboform_autoredirect': koboform.autoredirect
    }
