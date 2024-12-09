"""Utility functions for the SSSOM validation web application."""

import json
import logging
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from importlib.metadata import PackageNotFoundError, version
from io import StringIO
from typing import Callable

from sssom.constants import SchemaValidationType
from sssom.parsers import parse_sssom_table
from sssom.util import MappingSetDataFrame
from sssom.validators import validate
from sssom.writers import to_json, to_rdf_graph
from tsvalid.tsvalid import validates


class SSSOMValidation:
    """A class to encapsulate the results of SSSOM validation and conversion."""

    def __init__(self, sssom_text, limit_lines_displayed=5):
        """Initialize the SSSOMValidation object."""
        self.sssom_text = sssom_text
        self.limit_lines_displayed = limit_lines_displayed
        self.sssom_json = ""
        self.sssom_rdf = ""
        self.sssom_markdown = ""
        self.msdf = None
        self.sssom_validation_capture = StringIO()
        self.tsvalid_capture = StringIO()
        self.sssom_conversion_capture = StringIO()
        self.recognise_error_string = "**ERROR**:"
        self.recognise_warning_string = "**WARNING**:"

    def _run_sssom_conversion(self):
        if not self.msdf:
            raise ValueError("No SSSOM data frame loaded, run run_sssom_validation first.")

        msdf = self.msdf

        msdf_subset_for_display = MappingSetDataFrame(
            msdf.df.head(self.limit_lines_displayed),
            converter=msdf.converter,
            metadata=msdf.metadata,
        )
        msdf_subset_for_display.clean_prefix_map()

        self.sssom_json = json.dumps(to_json(msdf_subset_for_display), indent=4)

        if msdf.metadata.get("extension_definitions"):
            logging.warning(
                "Extension definitions are not supported in RDF output yet.\n"
                "This means that we could test if your code can be translated to RDF.\n"
                "Follow https://github.com/linkml/linkml/issues/2445 for updates."
            )
        else:
            self.sssom_rdf = (
                to_rdf_graph(msdf=msdf).serialize(format="turtle", encoding="utf-8").decode("utf-8")
            )

        self.sssom_markdown = msdf_subset_for_display.df.to_markdown(index=False)

    def _run_sssom_validation(self):
        validation_types = [
            SchemaValidationType.JsonSchema,
            SchemaValidationType.PrefixMapCompleteness,
            SchemaValidationType.StrictCurieFormat,
        ]
        self.msdf = parse_sssom_table(self.sssom_text)
        validate(msdf=self.msdf, validation_types=validation_types, fail_on_error=False)

    def _run_tsvalid_validation(self):
        validates(self.sssom_text, comment="#", exceptions=["W1"], summary=True, fail=False)

    def run(self):
        """Run the SSSOM validation and conversion."""
        run_with_capture(self.sssom_validation_capture, self._run_sssom_validation)
        run_with_capture(self.tsvalid_capture, self._run_tsvalid_validation)
        run_with_capture(self.sssom_conversion_capture, self._run_sssom_conversion)

    def get_tsvalid_report(self):
        """Get the tsvalid validation report."""
        return self._get_report(self.tsvalid_capture)

    def get_sssom_validation_report(self):
        """Get the SSSOM validation report."""
        return self._get_report(self.sssom_validation_capture)

    def get_sssom_conversion_report(self):
        """Get the SSSOM conversion report."""
        return self._get_report(self.sssom_conversion_capture)

    def _get_report(self, capture_stream):
        return capture_stream.getvalue() or "No issues detected."

    def is_ok_tsvalid(self):
        """Check if the tsvalid validation is OK."""
        return self.count_errors_tsvalid() == 0

    def is_ok_sssom_validation(self):
        """Check if the SSSOM validation is OK."""
        return self.count_errors_sssom_validation() == 0

    def is_ok_sssom_conversion(self):
        """Check if the SSSOM conversion is OK."""
        return self.count_errors_sssom_conversion() == 0

    def count_errors_tsvalid(self):
        """Check number of tsvalid errors."""
        return self._count_line_beginnings(self.get_tsvalid_report(), self.recognise_error_string)

    def count_errors_sssom_validation(self):
        """Check number of SSSOM errors."""
        return self._count_line_beginnings(
            self.get_sssom_validation_report(), self.recognise_error_string
        )

    def count_errors_sssom_conversion(self):
        """Check number of errors during SSSOM conversiomn."""
        return self._count_line_beginnings(
            self.get_sssom_conversion_report(), self.recognise_error_string
        )

    def count_warnings_tsvalid(self):
        """Check number of tsvalid errors."""
        return self._count_line_beginnings(self.get_tsvalid_report(), self.recognise_warning_string)

    def count_warnings_sssom_validation(self):
        """Check number of SSSOM errors."""
        return self._count_line_beginnings(
            self.get_sssom_validation_report(), self.recognise_warning_string
        )

    def count_warnings_sssom_conversion(self):
        """Check number of errors during SSSOM conversiomn."""
        return self._count_line_beginnings(
            self.get_sssom_conversion_report(), self.recognise_warning_string
        )

    def _count_line_beginnings(self, report, recognise_string):
        return sum(1 for line in report.splitlines() if line.startswith(recognise_string))

    def is_valid(self):
        """Check if the SSSOM file is valid overall, i.e. does not contain any errors."""
        return (
            self.is_ok_tsvalid() and self.is_ok_sssom_validation() and self.is_ok_sssom_conversion()
        )


# Helper function for logging configuration
@contextmanager
def configure_logger(capture_stream):
    """Configure logger to write to a stream."""
    logger = logging.getLogger()
    log_handler = logging.StreamHandler(capture_stream)
    log_handler.setLevel(logging.DEBUG)
    log_handler.setFormatter(logging.Formatter("**%(levelname)s**: %(message)s\n\n"))
    logger.addHandler(log_handler)
    try:
        yield
    finally:
        log_handler.flush()  # Ensure everything is written to the stream
        logger.removeHandler(log_handler)


def run_with_capture(capture, task_function: Callable, *args, **kwargs):
    """
    Run a task function within the context of stdout and stderr redirection and logger configuration.

    Args:
        capture: The capturing context (e.g., StringIO for stdout capture).
        task_function: The function to run within the context.
        *args: Positional arguments to pass to the task function.
        **kwargs: Keyword arguments to pass to the task function.
    """
    with redirect_stdout(capture), redirect_stderr(capture), configure_logger(capture):
        task_function(*args, **kwargs)


def generate_example():
    """Add an example to the input text area."""
    example = """# curie_map:
#   HP: http://purl.obolibrary.org/obo/HP_
#   MP: http://purl.obolibrary.org/obo/MP_
#   owl: http://www.w3.org/2002/07/owl#
#   rdf: http://www.w3.org/1999/02/22-rdf-syntax-ns#
#   rdfs: http://www.w3.org/2000/01/rdf-schemas#
#   semapv: https://w3id.org/semapv/vocab/
#   skos: http://www.w3.org/2004/02/skos/core#
#   sssom: https://w3id.org/sssom/
# license: https://creativecommons.org/publicdomain/zero/1.0/
# mapping_provider: http://purl.obolibrary.org/obo/upheno.owl
# mapping_set_id: https://w3id.org/sssom/mappings/27f85fe9-8a72-4e76-909b-7ba4244d9ede
subject_id	subject_label	predicate_id	object_id	object_label	mapping_justification
HP:0000175	Cleft palate	skos:exactMatch	MP:0000111	cleft palate	semapv:LexicalMatching
HP:0000252	Microcephaly	skos:exactMatch	MP:0000433	microcephaly	semapv:LexicalMatching
HP:0000260	 Wide anterior fontanel	skos:exactMatch	MP:0000085	large anterior fontanelle	semapv:LexicalMatching
HP:0000375	Abnormal cochlea morphology	skos:exactMatch	MP:0000031	abnormal cochlea morphology	semapv:LexicalMatching
HP:0000411	 Protruding ear	skos:exactBatch	MP:0000021	prominent ears	semapv:LexicalMatching
HP:0000822	Hypertension	skos:exactMatch	MP:0000231	hypertension	semapv:LexicalMatching"""
    return example


def get_package_version(package_name):
    """Get the version of a python package."""
    try:
        return version(package_name)
    except PackageNotFoundError:
        return f"{package_name} is not installed."
