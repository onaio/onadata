# -*- coding=utf-8 -*-
"""
Contians mock functions used in some tests for example enketo urls and exports
urls.
"""
import json

import requests
from httmock import urlmatch, all_requests


@urlmatch(netloc=r'(.*\.)?ona\.io$', path=r'^/examples/forms/tutorial/form$')
def xls_url_no_extension_mock(url, request):  # pylint: disable=unused-argument
    """
    Returns a mocked response object  for xls_url_no_extension_mock.
    """
    response = requests.Response()
    response.status_code = 200
    # pylint: disable=protected-access
    response._content = "success"
    # pylint: disable=line-too-long
    response.headers['content-disposition'] = 'attachment; filename="transportation_different_id_string.xlsx"; filename*=UTF-8\'\'transportation_different_id_string.xlsx'  # noqa
    response.headers['content-type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'  # noqa

    return response


# pylint: disable=invalid-name
@urlmatch(netloc=r'(.*\.)?ona\.io$', path=r'^/examples/forms/tutorial/form$')
def xls_url_no_extension_mock_content_disposition_attr_jumbled_v1(
        url, request):  # pylint: disable=unused-argument
    """
    Returns a mocked response object  for
    xls_url_no_extension_mock_content_disposition_attr_jumbled_v1.
    """
    response = requests.Response()
    response.status_code = 200
    # pylint: disable=protected-access
    response._content = "success"
    # pylint: disable=line-too-long
    response.headers['content-disposition'] = 'attachment; filename*=UTF-8\'\'transportation_different_id_string.xlsx; filename="transportation_different_id_string.xlsx"'  # noqa
    response.headers['content-type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'  # noqa

    return response


# pylint: disable=invalid-name
@urlmatch(netloc=r'(.*\.)?ona\.io$', path=r'^/examples/forms/tutorial/form$')
def xls_url_no_extension_mock_content_disposition_attr_jumbled_v2(
        url, request):  # pylint: disable=unused-argument
    """
    Returns a mocked response object  for
    xls_url_no_extension_mock_content_disposition_attr_jumbled_v2.
    """
    response = requests.Response()
    response.status_code = 200
    # pylint: disable=protected-access
    response._content = "success"
    # pylint: disable=line-too-long
    response.headers['content-disposition'] = 'filename*=UTF-8\'\'transportation_different_id_string.xlsx; attachment; filename="transportation_different_id_string.xlsx"'  # noqa
    response.headers['content-type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'  # noqa

    return response


@urlmatch(netloc=r'(.*\.)?enketo\.ona\.io$')
def enketo_mock(url, request):  # pylint: disable=unused-argument
    """
    Returns mocked Enketo Response object for all queries to enketo.ona.io.
    """
    response = requests.Response()
    response.status_code = 201
    # pylint: disable=protected-access
    response._content = \
        '{\n  "url": "https:\\/\\/dmfrm.enketo.org\\/webform",\n'\
        '  "code": "201"\n}'
    return response


@all_requests
def enketo_single_submission_mock(url, request):
    """Return mocked enketo single submission Response object."""
    response = requests.Response()
    response.status_code = 200
    # pylint: disable=protected-access
    response._content = \
        '{\n "single_url": "https:\\/\\/enketo.ona.io\\/single/::XZqoZ94y",\n'\
        '  "code": "200"\n}'
    return response


@urlmatch(netloc=r'(.*\.)?enketo\.ona\.io$', path=r'^/api_v1/survey/preview$')
def enketo_preview_url_mock(url, request):  # pylint: disable=unused-argument
    """
    Returns mocked Enketo Response object for all queries to enketo.ona.io for
    a preview link.
    """
    response = requests.Response()
    response.status_code = 201
    # pylint: disable=protected-access
    response._content = \
        '{\n  "preview_url": "https:\\/\\/enketo.ona.io\\/preview/::YY8M",\n'\
        '  "code": "201"\n}'
    return response


@urlmatch(netloc=r'(.*\.)?enketo\.ona\.io$', path=r'^/api_v1/survey$')
def enketo_url_mock(url, request):  # pylint: disable=unused-argument
    """
    Returns mocked Enketo Response object for all queries to enketo.ona.io to
    create an Enketo link.
    """
    response = requests.Response()
    response.status_code = 201
    # pylint: disable=protected-access
    response._content = \
        '{\n  "url": "https:\\/\\/enketo.ona.io\\/::YY8M",\n'\
        '  "code": "201"\n}'
    return response


@urlmatch(netloc=r'(.*\.)?enketo\.ona\.io$')
def enketo_error_mock(url, request):  # pylint: disable=unused-argument
    """
    Returns mocked Enketo Response object for all queries to enketo.ona.io that
    may result in an error response.
    """
    response = requests.Response()
    response.status_code = 400
    # pylint: disable=protected-access
    response._content = \
        '{\n  "message": "no account exists for this OpenRosa server",\n'\
        '  "code": "400"\n}'
    return response


@urlmatch(netloc=r'(.*\.)?enketo\.ona\.io$')
def enketo_error500_mock(url, request):  # pylint: disable=unused-argument
    """
    Returns mocked Enketo Response object for all queries to enketo.ona.io that
    may result in an HTTP 500 error response.
    """
    return {'status_code': 500,
            'content': "Something horrible happened."}


@urlmatch(netloc=r'(.*\.)?enketo\.ona\.io$')
def enketo_error502_mock(url, request):  # pylint: disable=unused-argument
    """
    Returns mocked Enketo Response object for all queries to enketo.ona.io that
    may result in an HTTP 500 error response.
    """
    return {'status_code': 502,
            'content': "Unavailable"}


@urlmatch(netloc=r'(.*\.)?enketo\.ona\.io$')
def enketo_mock_with_form_defaults(url, request):  # pylint: disable=W0613
    """
    Returns a mocked response for enketo.ona.io request for a link with form
    defaults.
    """
    response = requests.Response()
    response.status_code = 201
    # pylint: disable=protected-access
    response._content = \
        '{\n  "url": "https:\\/\\/dmfrm.enketo.org\\/webform?d[%2Fnum]=1",\n'\
        '  "code": "200"\n}'
    return response


@urlmatch(netloc=r'(.*\.)?xls_server$')
def external_mock(url, request):  # pylint: disable=unused-argument
    """
    Returns mocked Response object for accessing XLS reports server.
    """
    assert 'transport_available_transportation_types_to_referral_facility'\
           in request.body, ""
    response = requests.Response()
    response.status_code = 201
    # pylint: disable=protected-access
    response._content = b"/xls/ee3ff9d8f5184fc4a8fdebc2547cc059"
    return response


# pylint: disable=unused-argument
@urlmatch(netloc=r'(.*\.)?xls_server$')
def external_mock_single_instance(url, request, uuid=None):
    """
    Returns mocked Response object for accessing XLS reports server.
    """
    payload = json.loads(request.body)
    assert payload
    assert len(payload) == 1
    assert '_id' in payload[0]
    assert 'transport_loop_over_transport_types_frequency_ambulance_' \
           'frequency_to_referral_facility' in payload[0]
    assert payload[0].get('transport_available_transportation_types_to'
                          '_referral_facility') == "ambulance bicycle"
    response = requests.Response()
    response.status_code = 201
    # pylint: disable=protected-access
    response._content = b"/xls/ee3ff9d8f5184fc4a8fdebc2547cc059"
    return response


@urlmatch(netloc=r'(.*\.)?xls_server$')
def external_mock_single_instance2(url, request, uuid=None):
    """
    Returns mocked Response object for accessing XLS reports server.
    """
    payload = json.loads(request.body)
    assert payload
    assert len(payload) == 1
    assert '_id' in payload[0]
    assert 'transport_loop_over_transport_types_frequency_ambulance_' \
           'frequency_to_referral_facility' in payload[0]
    assert payload[0].get('transport_available_transportation_types_to'
                          '_referral_facility') == "ambulance bicycle"
    response = requests.Response()
    response.status_code = 201
    # pylint: disable=protected-access
    response._content = b"/xls/ee3ff9d8f5184fc4a8fdebc2547cc057"
    return response
