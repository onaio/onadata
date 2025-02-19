# -*- coding: utf-8 -*-
"""
PyxformTestCase base class using markdown to define the XLSForm.
"""
import codecs
import logging
import os
import tempfile
from dataclasses import dataclass
from typing import TYPE_CHECKING
from unittest import TestCase

from lxml import etree
from pyxform.builder import create_survey_element_from_dict
from pyxform.constants import NSMAP
from pyxform.errors import PyXFormError
from pyxform.validators.odk_validate import ODKValidateError, check_xform
from pyxform.xls2json import workbook_to_json
from pyxform.xls2json_backends import DefinitionData, md_to_dict

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)

# noinspection PyProtectedMember
_Element = etree._Element  # pylint: disable=protected-access


if TYPE_CHECKING:
    from typing import Dict, List, Set, Tuple, Union

    NSMAPSubs: "List[Tuple[str, str]]"


class PyxformTestError(Exception):
    """Pyxform test errors exception class."""


@dataclass
class MatcherContext:
    """Data class to store assertion context information."""

    debug: bool
    nsmap_xpath: "Dict[str, str]"
    nsmap_subs: "NSMAPSubs"  # noqa: F821
    content_str: str


class PyxformMarkdown:  # pylint: disable=too-few-public-methods
    """Transform markdown formatted XLSForm to a pyxform survey object"""

    def md_to_pyxform_survey(self, md_raw, kwargs=None, autoname=True, warnings=None):
        """Transform markdown formatted XLSForm to pyxform survey object."""
        if kwargs is None:
            kwargs = {}
        if autoname:
            kwargs = self._autoname_inputs(kwargs)
        workbook_json = workbook_to_json(
            DefinitionData(
                fallback_form_name=kwargs.get("name", "data"), **md_to_dict(md_raw)
            ),
            form_name=kwargs.get("name", "data"),
            fallback_form_name=kwargs.get("name", "data"),
            warnings=warnings,
        )
        if "id_string" in kwargs:
            workbook_json["id_string"] = kwargs["id_string"]
        return create_survey_element_from_dict(workbook_json)

    @staticmethod
    def _run_odk_validate(xml):
        # On Windows, NamedTemporaryFile must be opened exclusively.
        # So it must be explicitly created, opened, closed, and removed
        # pylint: disable=consider-using-with
        tmp = tempfile.NamedTemporaryFile(suffix=".xml", delete=False)
        tmp.close()
        try:
            with codecs.open(tmp.name, mode="w", encoding="utf-8") as file_handle:
                file_handle.write(xml)
                file_handle.close()
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
    """The pyxform markdown TestCase class"""

    maxDiff = None

    # pylint: disable=invalid-name,too-many-locals,too-many-branches,too-many-statements
    def assertPyxformXform(self, **kwargs):  # noqa
        """
        PyxformTestCase.assertPyxformXform() named arguments:
        -----------------------------------------------------

        one of these possible survey input types
          * md: (str) a markdown formatted xlsform (easy to read in code)
                [consider a plugin to help with formatting md tables,
                 e.g. https://github.com/vkocubinsky/SublimeTableEditor]
          * survey: (pyxform.survey.Survey) easy for reuse within a test
          # Note: XLS is not implemented at this time. You can use builder to
          create a pyxform Survey object

        one or many of these string "matchers":
          * xml__contains: an array of strings which exist in the
                resulting xml. [xml|model|instance|itext]_excludes are also
                supported.
          * error__contains: a list of strings which should exist in the error
          * error__not_contains: a list of strings which should not exist in
                                 the error
          * odk_validate_error__contains: list of strings; run_odk_validate
                                           must be set
          * warnings__contains: a list of strings which should exist in the
               warnings
          * warnings__not_contains: a list of strings which should not
               exist in the warnings
          * warnings_count: the number of expected warning messages
          * xml__excludes: an array of strings which should not exist in the
               resulting xml. [xml|model|instance|itext]_excludes are also
               supported.
          * xml__xpath_exact: A list of tuples where the first tuple element
               is an XPath expression and the second tuple element is a
               set of exact string match results that are expected.
          * xml__xpath_count: A list of tuples where the first tuple element
               is_an XPath expression and the second tuple element is the
               integer number of match results that are expected.
          * xml__xpath_match: A list of XPath expression strings for which
               exactly one match result each is expected. Effectively a
               shortcut for xml__xpath_count with a count of 1.

        For each of the xpath_* matchers above, if the XPath expression
        is looking for an element in the 'default' namespace (xforms) then
        use an 'x' namespace prefix for the element. For example to find
        input nodes in the body: ".//h:body/x:input". This 'x' prefix is
        not required for attributes. When writing a xpath_* test, use
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
          * debug: (bool) when True, log details of the test to stdout.
                Details include the input survey markdown, the XML document,
                XPath match strings.
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
            if "md" in kwargs:
                kwargs = self._autoname_inputs(kwargs)
                survey = self.md_to_pyxform_survey(
                    kwargs.get("md"), kwargs, warnings=warnings
                )
            else:
                survey = kwargs.get("survey")

            xml = survey._to_pretty_xml()  # pylint: disable=protected-access
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
                    f".//n:{element_selector}",
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
                ) from e
            for v_err in odk_validate_error__contains:
                self.assertContains(
                    e.args[0], v_err, msg_prefix="odk_validate_error__contains"
                )

        if survey_valid:

            def _check(keyword, verb):
                verb_str = f"{keyword}__{verb}"

                bad_kwarg = f"{code}_{verb}"
                if bad_kwarg in kwargs:
                    good_kwarg = f"{code}__{verb}"
                    raise SyntaxError(
                        (
                            f"'{bad_kwarg}' is not a valid parameter. "
                            f"Use double underscores: '{good_kwarg}'"
                        )
                    )

                def check_content(content, expected):
                    if content is None:
                        self.fail(msg=f"No '{keyword}' found in document.")
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
                    "Invalid parameter: 'body__contains'.Use 'xml__contains' instead"
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
        if survey_valid and expecting_invalid_survey:
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
                raise PyxformTestError(f"Unexpected search test kwarg: {k}")
            if k.startswith("error"):
                joined = "\n".join(errors)
            elif k.startswith("warnings"):
                joined = "\n".join(warnings)
            else:
                raise PyxformTestError(f"Unexpected search test kwarg: {k}")
            for text in kwargs[k]:
                assertion(joined, text, msg_prefix=k)
        if "warnings_count" in kwargs:
            c = kwargs.get("warnings_count")
            if not isinstance(c, int):
                raise PyxformTestError("warnings_count must be an integer.")
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

    def assertContains(self, content, text, count=None, msg_prefix=""):  # noqa
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
                msg_prefix + f"Found {real_count} instances of {text_repr} in content"
                f" (expected {count})",
            )
        else:
            self.assertTrue(
                real_count != 0,
                msg_prefix + f"Couldn't find {text_repr + content} in content:\n",
            )

    def assertNotContains(self, content, text, msg_prefix=""):  # noqa
        """
        Asserts that a content indicates that some content was retrieved
        successfully, (i.e., the HTTP status code was as expected), and that
        ``text`` doesn't occurs in the content of the content.
        """
        text_repr, real_count, msg_prefix = self._assert_contains(
            content, text, msg_prefix
        )

        self.assertEqual(
            real_count,
            0,
            msg_prefix + f"Response should not contain {text_repr}",
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

        Compares result strings since expected strings may contain xml namespace
        prefixes.
        To allow parsing required to compare as ETrees would require injecting
        namespace declarations into the expected match strings.

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
        msg = (
            f"XPath found no matches:\n{xpath}\n\n"
            f"XForm content:\n{matcher_context.content_str}"
        )
        self.assertEqual(expected, len(observed), msg=msg)


def reorder_attributes(root):
    """
    Forces alphabetical ordering of all XML attributes to match pre Python 3.8
    behaviour. In general, we should not rely on ordering, but changing all the
    tests is not realistic at this moment.

    See bottom of https://bit.ly/38docMg and
    https://bit.ly/3ODx9iG for more information.

    NOTE: there's a similar ordering change made in utils.node. This one is
    also needed because in assertPyxformXform, the survey is converted to XML
    and then read back in using ETree.fromstring. This means that attribute
    ordering here is based on the attribute representation of
    xml.etree.ElementTree objects.
    In utils.node, it is based on xml.dom.minidom.Element objects.
    See https://github.com/XLSForm/pyxform/issues/414.
    """
    for elem in root.iter():
        attrib = elem.attrib
        if len(attrib) > 1:
            # Sort attributes. Attributes are represented as {namespace}name
            # so attributes with explicit namespaces will always sort after
            # those without explicit namespaces.
            attribs = sorted(attrib.items())
            attrib.clear()
            attrib.update(attribs)


def xpath_clean_result_strings(
    nsmap_subs: "NSMAPSubs", results: "Set[_Element]"  # noqa: F821
) -> "Set[str]":
    """
    Clean XPath results: stringify, remove namespace declarations, clean up whitespace.

    :param nsmap_subs: namespace replacements e.g.
                            [('x="http://www.w3.org/2002/xforms", "")]
    :param results: XPath results to clean.
    """
    xmlex = [(" >", ">"), (" />", "/>")]
    subs = nsmap_subs + xmlex
    cleaned = set()
    for result in results:
        if isinstance(result, _Element):
            reorder_attributes(result)
            result = etree.tostring(result, encoding=str, pretty_print=True)
            result = result.strip()
            for sub in subs:
                result = result.replace(*sub)
        cleaned.add(result)
    return cleaned


def xpath_evaluate(
    matcher_context: "MatcherContext",
    content: "_Element",
    xpath: str,
    for_exact=False,
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
    except etree.XPathEvalError as error:
        msg = f"Error processing XPath: {xpath}\n" + "\n".join(error.args)
        raise PyxformTestError(msg) from error
    if matcher_context.debug:
        if 0 == len(results):
            logger.debug("Results for XPath: %s\n(No matches)\n", xpath)
        else:
            cleaned = xpath_clean_result_strings(
                nsmap_subs=matcher_context.nsmap_subs, results=results
            )
            logger.debug("Results for XPath: %s\n%s\n", xpath, "\n".join(cleaned))
    if for_exact:
        return xpath_clean_result_strings(
            nsmap_subs=matcher_context.nsmap_subs, results=results
        )
    return set(results)
