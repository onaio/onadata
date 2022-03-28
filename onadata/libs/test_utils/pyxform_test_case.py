# -*- coding: utf-8 -*-
"""
PyxformTestCase base class using markdown to define the XLSForm.
"""
import codecs
import logging
import os
import re
import tempfile
from dataclasses import dataclass
from typing import TYPE_CHECKING
from unittest import TestCase

from lxml import etree

# noinspection PyProtectedMember
from lxml.etree import _Element

from pyxform.builder import create_survey_element_from_dict
from pyxform.errors import PyXFormError
from pyxform.utils import NSMAP
from pyxform.validators.odk_validate import ODKValidateError, check_xform
from pyxform.xls2json import workbook_to_json
from onadata.libs.test_utils.md_table import md_table_to_ss_structure

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)


if TYPE_CHECKING:
    from typing import Dict, List, Set, Tuple, Union

    NSMAPSubs: "List[Tuple[str, str]]"


class PyxformTestError(Exception):
    pass


@dataclass
class MatcherContext:
    debug: bool
    nsmap_xpath: "Dict[str, str]"
    nsmap_subs: "NSMAPSubs"
    content_str: str


class PyxformMarkdown:
    """Transform markdown formatted xlsform to a pyxform survey object"""

    def md_to_pyxform_survey(self, md_raw, kwargs=None, autoname=True, warnings=None):
        if kwargs is None:
            kwargs = {}
        if autoname:
            kwargs = self._autoname_inputs(kwargs)
        _md = []
        for line in md_raw.split("\n"):
            if re.match(r"^\s+#", line):
                # ignore lines which start with pound sign
                continue
            elif re.match(r"^(.*)(#[^|]+)$", line):
                # keep everything before the # outside of the last occurrence
                # of |
                _md.append(re.match(r"^(.*)(#[^|]+)$", line).groups()[0].strip())
            else:
                _md.append(line.strip())
        md = "\n".join(_md)

        if kwargs.get("debug"):
            logger.debug(md)

        def list_to_dicts(arr):
            headers = arr[0]

            def _row_to_dict(row):
                out_dict = {}
                for i in range(0, len(row)):
                    col = row[i]
                    if col not in [None, ""]:
                        out_dict[headers[i]] = col
                return out_dict

            return [_row_to_dict(r) for r in arr[1:]]

        sheets = {}
        for sheet, contents in md_table_to_ss_structure(md):
            sheets[sheet] = list_to_dicts(contents)

        return self._ss_structure_to_pyxform_survey(sheets, kwargs, warnings=warnings)

    @staticmethod
    def _ss_structure_to_pyxform_survey(ss_structure, kwargs, warnings=None):
        # using existing methods from the builder
        imported_survey_json = workbook_to_json(ss_structure, warnings=warnings)
        # ideally, when all these tests are working, this would be
        # refactored as well
        survey = create_survey_element_from_dict(imported_survey_json)
        survey.name = kwargs.get("name", "data")
        survey.title = kwargs.get("title")
        survey.id_string = kwargs.get("id_string")

        return survey

    @staticmethod
    def _run_odk_validate(xml):
        # On Windows, NamedTemporaryFile must be opened exclusively.
        # So it must be explicitly created, opened, closed, and removed
        tmp = tempfile.NamedTemporaryFile(suffix=".xml", delete=False)
        tmp.close()
        try:
            with codecs.open(tmp.name, mode="w", encoding="utf-8") as fp:
                fp.write(xml)
                fp.close()
            check_xform(tmp.name)
        finally:
            # Clean up the temporary file
            os.remove(tmp.name)
            assert not os.path.isfile(tmp.name)

    @staticmethod
    def _autoname_inputs(kwargs):
        """
        title and name are necessary for surveys, but not always convenient to
        include in test cases, so this will pull a default value
        from the stack trace.
        """
        test_name_root = "pyxform"
        if "name" not in kwargs.keys():
            kwargs["name"] = test_name_root + "_autotestname"
        if "title" not in kwargs.keys():
            kwargs["title"] = test_name_root + "_autotesttitle"
        if "id_string" not in kwargs.keys():
            kwargs["id_string"] = test_name_root + "_autotest_id_string"

        return kwargs


class PyxformTestCase(PyxformMarkdown, TestCase):
    maxDiff = None

    def assertPyxformXform(self, **kwargs):
        """
        PyxformTestCase.assertPyxformXform() named arguments:
        -----------------------------------------------------

        one of these possible survey input types
          * md: (str) a markdown formatted xlsform (easy to read in code)
                [consider a plugin to help with formatting md tables,
                 e.g. https://github.com/vkocubinsky/SublimeTableEditor]
          * ss_structure: (dict) a python dictionary with sheets and their
                contents. best used in cases where testing whitespace and
                cells' type is important
          * survey: (pyxform.survey.Survey) easy for reuse within a test
          # Note: XLS is not implemented at this time. You can use builder to
          create a pyxform Survey object

        one or many of these string "matchers":
          * xml__contains: an array of strings which exist in the
                resulting xml. [xml|model|instance|itext]_excludes are also supported.
          * error__contains: a list of strings which should exist in the error
          * error__not_contains: a list of strings which should not exist in the error
          * odk_validate_error__contains: list of strings; run_odk_validate must be set
          * warnings__contains: a list of strings which should exist in the warnings
          * warnings__not_contains: a list of strings which should not exist in the warnings
          * warnings_count: the number of expected warning messages
          * xml__excludes: an array of strings which should not exist in the resulting
               xml. [xml|model|instance|itext]_excludes are also supported.
          * xml__xpath_exact: A list of tuples where the first tuple element is an XPath
               expression and the second tuple element is a set of exact string match
               results that are expected.
          * xml__xpath_count: A list of tuples where the first tuple element is an XPath
               expression and the second tuple element is the integer number of match
               results that are expected.
          * xml__xpath_match: A list of XPath expression strings for which exactly one
               match result each is expected. Effectively a shortcut for
               xml__xpath_count with a count of 1.

        For each of the xpath_* matchers above, if the XPath expression is looking for an
        element in the 'default' namespace (xforms) then use an 'x' namespace prefix for
        the element. For example to find input nodes in the body: ".//h:body/x:input".
        This 'x' prefix is not required for attributes. When writing a xpath_* test, use
        debug=True to show the XPath match results.

        optional other parameters passed to pyxform:
          * errored: (bool) if the xlsform is not supposed to compile,
                this must be True
          * name: (str) a valid xml tag to be used as the form name
          * id_string: (str)
          * title: (str)
          * run_odk_validate: (bool) when True, runs ODK Validate process
                Default value = False because it slows down tests
          * warnings: (list) a list to use for storing warnings for inspection.
          * debug: (bool) when True, log details of the test to stdout. Details include
                the input survey markdown, the XML document, XPath match strings.
        """
        debug = kwargs.get("debug", False)
        expecting_invalid_survey = kwargs.get("errored", False)
        errors = []
        warnings = kwargs.get("warnings", [])
        xml_nodes = {}

        run_odk_validate = kwargs.get("run_odk_validate", False)
        odk_validate_error__contains = kwargs.get("odk_validate_error__contains", [])
        survey_valid = True

        try:
            if "md" in kwargs.keys():
                kwargs = self._autoname_inputs(kwargs)
                survey = self.md_to_pyxform_survey(
                    kwargs.get("md"), kwargs, warnings=warnings
                )
            elif "ss_structure" in kwargs.keys():
                kwargs = self._autoname_inputs(kwargs)
                survey = self._ss_structure_to_pyxform_survey(
                    kwargs.get("ss_structure"),
                    kwargs,
                    warnings=warnings,
                )
            else:
                survey = kwargs.get("survey")

            xml = survey._to_pretty_xml()
            root = etree.fromstring(xml.encode("utf-8"))

            # Ensure all namespaces are present, even if unused
            survey_nsmap = survey.get_nsmap()
            final_nsmap = NSMAP.copy()
            final_nsmap.update(survey_nsmap)
            root.nsmap.update(final_nsmap)
            final_nsmap_xpath = {
                "x": final_nsmap["xmlns"],
                **{k.split(":")[1]: v for k, v in final_nsmap.items() if k != "xmlns"},
            }
            final_nsmap_subs = [(f' {k}="{v}"', "") for k, v in final_nsmap.items()]
            # guarantee that strings contain alphanumerically sorted attributes across
            # Python versions
            reorder_attributes(root)

            xml_nodes["xml"] = root

            def _pull_xml_node_from_root(element_selector):
                _r = root.findall(
                    ".//n:%s" % element_selector,
                    namespaces={"n": "http://www.w3.org/2002/xforms"},
                )
                if _r:
                    return _r[0]

                return False

            for _n in ["model", "instance", "itext"]:
                xml_nodes[_n] = _pull_xml_node_from_root(_n)
            if debug:
                logger.debug(xml)
            if run_odk_validate:
                self._run_odk_validate(xml=xml)
                if odk_validate_error__contains:
                    raise PyxformTestError("ODKValidateError was not raised")

        except PyXFormError as e:
            survey_valid = False
            errors = [str(e)]
            if debug:
                logger.debug("<xml unavailable />")
                logger.debug("ERROR: '%s'", errors[0])
        except ODKValidateError as e:
            if not odk_validate_error__contains:
                raise PyxformTestError(
                    "ODK Validate error was thrown but "
                    + "'odk_validate_error__contains'"
                    + " was empty:"
                    + str(e)
                )
            for v_err in odk_validate_error__contains:
                self.assertContains(
                    e.args[0], v_err, msg_prefix="odk_validate_error__contains"
                )

        if survey_valid:

            def _check(keyword, verb):
                verb_str = "%s__%s" % (keyword, verb)

                bad_kwarg = "%s_%s" % (code, verb)
                if bad_kwarg in kwargs:
                    good_kwarg = "%s__%s" % (code, verb)
                    raise SyntaxError(
                        (
                            "'%s' is not a valid parameter. "
                            "Use double underscores: '%s'"
                        )
                        % (bad_kwarg, good_kwarg)
                    )

                def check_content(content, expected):
                    if content is None:
                        self.fail(msg="No '{}' found in document.".format(keyword))
                    cstr = etree.tostring(content, encoding=str, pretty_print=True)
                    matcher_context = MatcherContext(
                        debug=debug,
                        nsmap_xpath=final_nsmap_xpath,
                        nsmap_subs=final_nsmap_subs,
                        content_str=cstr,
                    )
                    for i in expected:
                        if verb == "contains":
                            self.assertContains(cstr, i, msg_prefix=keyword)
                        elif verb == "excludes":
                            self.assertNotContains(cstr, i, msg_prefix=keyword)
                        elif verb == "xpath_exact":
                            self.assert_xpath_exact(
                                matcher_context=matcher_context,
                                content=content,
                                xpath=i[0],
                                expected=i[1],
                            )
                        elif verb == "xpath_count":
                            self.assert_xpath_count(
                                matcher_context=matcher_context,
                                content=content,
                                xpath=i[0],
                                expected=i[1],
                            )
                        elif verb == "xpath_match":
                            self.assert_xpath_count(
                                matcher_context=matcher_context,
                                content=content,
                                xpath=i,
                                expected=1,
                            )

                return verb_str, check_content

            if "body_contains" in kwargs or "body__contains" in kwargs:
                raise SyntaxError(
                    "Invalid parameter: 'body__contains'." "Use 'xml__contains' instead"
                )

            for code in ["xml", "instance", "model", "itext"]:
                for _verb in ["contains", "excludes"]:
                    (code__str, checker) = _check(code, _verb)
                    if kwargs.get(code__str):
                        checker(xml_nodes[code], kwargs[code__str])

            for xpath_verb in ("xpath_exact", "xpath_count", "xpath_match"):
                code__str, checker = _check("xml", xpath_verb)
                if kwargs.get(code__str) is not None:
                    checker(xml_nodes["xml"], kwargs[code__str])

        if not survey_valid and not expecting_invalid_survey:
            raise PyxformTestError(
                "Expected valid survey but compilation failed. "
                "Try correcting the error with 'debug=True', "
                "setting 'errored=True', "
                "and or optionally 'error__contains=[...]'"
                "\nError(s): " + "\n".join(errors)
            )
        elif survey_valid and expecting_invalid_survey:
            raise PyxformTestError("Expected survey to be invalid.")

        search_test_kwargs = (
            "error__contains",
            "error__not_contains",
            "warnings__contains",
            "warnings__not_contains",
        )
        for k in search_test_kwargs:
            if k not in kwargs:
                continue
            if k.endswith("__contains"):
                assertion = self.assertContains
            elif k.endswith("__not_contains"):
                assertion = self.assertNotContains
            else:
                raise PyxformTestError("Unexpected search test kwarg: {}".format(k))
            if k.startswith("error"):
                joined = "\n".join(errors)
            elif k.startswith("warnings"):
                joined = "\n".join(warnings)
            else:
                raise PyxformTestError("Unexpected search test kwarg: {}".format(k))
            for text in kwargs[k]:
                assertion(joined, text, msg_prefix=k)
        if "warnings_count" in kwargs:
            c = kwargs.get("warnings_count")
            if not isinstance(c, int):
                PyxformTestError("warnings_count must be an integer.")
            self.assertEqual(c, len(warnings))

    @staticmethod
    def _assert_contains(content, text, msg_prefix):
        if msg_prefix:
            msg_prefix += ": "

        # Account for space in self-closing tags
        text_repr = repr(text)
        content = content.replace(" />", "/>")
        real_count = content.count(text)

        return text_repr, real_count, msg_prefix

    def assertContains(self, content, text, count=None, msg_prefix=""):
        """
        FROM: django source- testcases.py

        Asserts that ``text`` occurs ``count`` times in the content string.
        If ``count`` is None, the count doesn't matter - the assertion is
        true if the text occurs at least once in the content.
        """
        text_repr, real_count, msg_prefix = self._assert_contains(
            content, text, msg_prefix
        )

        if count is not None:
            self.assertEqual(
                real_count,
                count,
                msg_prefix + "Found %d instances of %s in content"
                " (expected %d)" % (real_count, text_repr, count),
            )
        else:
            self.assertTrue(
                real_count != 0,
                msg_prefix + "Couldn't find %s in content:\n" % text_repr + content,
            )

    def assertNotContains(self, content, text, msg_prefix=""):
        """
        Asserts that a content indicates that some content was retrieved
        successfully, (i.e., the HTTP status code was as expected), and that
        ``text`` doesn't occurs in the content of the content.
        """
        text_repr, real_count, msg_prefix = self._assert_contains(
            content, text, msg_prefix
        )

        self.assertEqual(
            real_count, 0, msg_prefix + "Response should not contain %s" % text_repr
        )

    def assert_xpath_exact(
        self,
        matcher_context: "MatcherContext",
        content: "_Element",
        xpath: str,
        expected: "Set[str]",
    ) -> None:
        """
        Process an assertion for xml__xpath_exact.

        Compares result strings since expected strings may contain xml namespace prefixes.
        To allow parsing required to compare as ETrees would require injecting namespace
        declarations into the expected match strings.

        :param matcher_context: A MatcherContext dataclass.
        :param content: XML to be examined.
        :param xpath: XPath to execute.
        :param expected: Expected XPath matches, as XML fragments.
        """
        if not (isinstance(xpath, str) and isinstance(expected, set)):
            msg = "Each xpath_exact requires: tuple(xpath: str, expected: Set[str])."
            raise SyntaxError(msg)
        observed = xpath_evaluate(
            matcher_context=matcher_context,
            content=content,
            xpath=xpath,
            for_exact=True,
        )
        self.assertSetEqual(set(expected), observed, matcher_context.content_str)

    def assert_xpath_count(
        self,
        matcher_context: "MatcherContext",
        content: "_Element",
        xpath: str,
        expected: int,
    ):
        """
        Process an assertion for xml__xpath_count.

        :param matcher_context: A MatcherContext dataclass.
        :param content: XML to be examined.
        :param xpath: XPath to execute.
        :param expected: Expected count of XPath matches.
        """
        if not (isinstance(xpath, str) and isinstance(expected, int)):
            msg = "Each xpath_count requires: tuple(xpath: str, count: int)"
            raise SyntaxError(msg)
        observed = xpath_evaluate(
            matcher_context=matcher_context,
            content=content,
            xpath=xpath,
        )
        msg = f"XPath found no matches:\n{xpath}\n\nXForm content:\n{matcher_context.content_str}"
        self.assertEqual(expected, len(observed), msg=msg)


def reorder_attributes(root):
    """
    Forces alphabetical ordering of all XML attributes to match pre Python 3.8 behavior.
    In general, we should not rely on ordering, but changing all the tests is not
    realistic at this moment.

    See bottom of https://docs.python.org/3/library/xml.etree.elementtree.html#element-objects and
    https://github.com/python/cpython/commit/a3697db0102b9b6747fe36009e42f9b08f0c1ea8 for more information.

    NOTE: there's a similar ordering change made in utils.node. This one is also needed because in
    assertPyxformXform, the survey is converted to XML and then read back in using ETree.fromstring. This
    means that attribute ordering here is based on the attribute representation of xml.etree.ElementTree objects.
    In utils.node, it is based on xml.dom.minidom.Element objects. See https://github.com/XLSForm/pyxform/issues/414.
    """
    for el in root.iter():
        attrib = el.attrib
        if len(attrib) > 1:
            # Sort attributes. Attributes are represented as {namespace}name so attributes with explicit
            # namespaces will always sort after those without explicit namespaces.
            attribs = sorted(attrib.items())
            attrib.clear()
            attrib.update(attribs)


def xpath_clean_result_strings(
    nsmap_subs: "NSMAPSubs", results: "Set[_Element]"
) -> "Set[str]":
    """
    Clean XPath results: stringify, remove namespace declarations, clean up whitespace.

    :param nsmap_subs: namespace replacements e.g. [('x="http://www.w3.org/2002/xforms", "")]
    :param results: XPath results to clean.
    """
    xmlex = [(" >", ">"), (" />", "/>")]
    subs = nsmap_subs + xmlex
    cleaned = set()
    for x in results:
        if isinstance(x, _Element):
            reorder_attributes(x)
            x = etree.tostring(x, encoding=str, pretty_print=True)
            x = x.strip()
            for s in subs:
                x = x.replace(*s)
        cleaned.add(x)
    return cleaned


def xpath_evaluate(
    matcher_context: "MatcherContext", content: "_Element", xpath: str, for_exact=False
) -> "Union[Set[_Element], Set[str]]":
    """
    Evaluate an XPath and return the results.

    :param matcher_context: A MatcherContext dataclass.
    :param content: XML to be examined.
    :param xpath: XPath to execute.
    :param for_exact: If True, convert the results to strings and perform clean-up. If
      False, return the set of Element (or attribute string) matches as-is.
    :return:
    """
    try:
        results = content.xpath(xpath, namespaces=matcher_context.nsmap_xpath)
    except etree.XPathEvalError as e:
        msg = f"Error processing XPath: {xpath}\n" + "\n".join(e.args)
        raise PyxformTestError(msg) from e
    if matcher_context.debug:
        if 0 == len(results):
            logger.debug(f"Results for XPath: {xpath}\n" + "(No matches)" + "\n")
        else:
            cleaned = xpath_clean_result_strings(
                nsmap_subs=matcher_context.nsmap_subs, results=results
            )
            logger.debug(f"Results for XPath: {xpath}\n" + "\n".join(cleaned) + "\n")
    if for_exact:
        return xpath_clean_result_strings(
            nsmap_subs=matcher_context.nsmap_subs, results=results
        )
    else:
        return set(results)
