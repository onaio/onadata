# -*- coding=utf-8 -*-
"""
FLOIP utility functions.
"""

QUESTION_TYPE = {
    "multiple_choice": "select_one",
    "numeric": "integer",
    "open": "text",
    "geo_point": "geopoint"
}


def floip_to_markdown(name, question_options):
    """
    Returns XLSForm markdown string given a question.
    """
    assert isinstance(question_options, dict), "Expecting a dict."
    assert "type" in question_options, "'type' is missing in %s." % (
        question_options)
    assert "label" in question_options, "'label' is missing in %s." % (
        question_options)

    question_type = QUESTION_TYPE[question_options['type']]
    label = question_options['label']
    question_md = "%s | %s | %s" % (name, question_type, label)

    return question_md
