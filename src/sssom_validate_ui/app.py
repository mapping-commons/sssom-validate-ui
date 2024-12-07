"""Simple streamlit app for validating SSSOM files."""

import logging
import sys
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from importlib.metadata import PackageNotFoundError, version
from io import StringIO

import pandas as pd
import streamlit as st
from linkml.generators.pythongen import PythonGenerator
from linkml.validators.jsonschemavalidator import JsonSchemaDataValidator
from sssom.constants import SCHEMA_YAML, SchemaValidationType
from sssom.parsers import parse_sssom_table, to_mapping_set_document
from sssom.util import MappingSetDataFrame
from sssom.validators import validate
from tsvalid.tsvalid import validates

sys.tracebacklimit = 0


def validate_linkml(msdf: MappingSetDataFrame):
    """Validate the contents of the mapping set using the LinkML JSON Schema validator."""
    mod = PythonGenerator(SCHEMA_YAML).compile_module()
    validator = JsonSchemaDataValidator(schema=SCHEMA_YAML)

    mapping_set = to_mapping_set_document(msdf).mapping_set
    result = validator.validate_object(mapping_set, target_class=mod.MappingSet)
    return result


def validate_sssom(sssom_text_str, limit_lines_displayed=5):
    """Validate a mapping set using SSSOM and tsvalid validations."""
    # Capture logs for SSSOM validation
    sssom_validation_capture = StringIO()
    sssom_text = StringIO(sssom_text_str)
    sssom_json = {"mapping_set_id": "NONE"}
    sssom_rdf = "NONE"
    pd.set_option("future.no_silent_downcasting", True)
    with redirect_stdout(sssom_validation_capture), redirect_stderr(
        sssom_validation_capture
    ), configure_logger(sssom_validation_capture):
        validation_types = [
            SchemaValidationType.JsonSchema,
            SchemaValidationType.PrefixMapCompleteness,
            SchemaValidationType.StrictCurieFormat,
        ]
        msdf = parse_sssom_table(sssom_text)
        validate(msdf=msdf, validation_types=validation_types, fail_on_error=False)
        msdf_subset_for_display = MappingSetDataFrame(
            msdf.df.head(limit_lines_displayed), converter=msdf.converter, metadata=msdf.metadata
        )
        msdf_subset_for_display.clean_prefix_map()
        from sssom.writers import to_json, to_rdf_graph

        sssom_json = to_json(msdf_subset_for_display)
        if msdf.metadata.get("extension_definitions"):
            logging.warning(
                "Extension definitions are not supported in RDF output yet.\n"
                "This means that we could test if your code can be translated to RDF.\n"
                "Follow https://github.com/linkml/linkml/issues/2445 for updates."
            )
            sssom_rdf = None
        else:
            sssom_rdf = (
                to_rdf_graph(msdf=msdf).serialize(format="turtle", encoding="utf-8").decode("utf-8")
            )
        sssom_markdown = msdf_subset_for_display.df.to_markdown(index=False)
    log_output = sssom_validation_capture.getvalue() or "No validation issues detected."
    sssom_ok = "No validation issues detected." in log_output

    # Capture logs for tsvalid validation
    tsvalid_capture = StringIO()
    with redirect_stdout(tsvalid_capture), redirect_stderr(tsvalid_capture), configure_logger(
        tsvalid_capture
    ):
        validates(sssom_text, comment="#", exceptions=[], summary=True, fail=False)

    # Restore outputs and get results
    tsvalid_report = tsvalid_capture.getvalue() or "No validation issues detected."
    tsvalid_ok = "No validation issues detected." in tsvalid_report
    # Compile the validation report

    report = ""

    if sssom_ok and tsvalid_ok:
        report = "No validation issues detected."
    else:
        report = "Some problems where found with your file."
        if not sssom_ok:
            report += f"\n\n### SSSOM report\n\nFor more information see [SSSOM documentation](https://mapping-commons.github.io/sssom/linkml-index/)\n\n{log_output}"
        if not tsvalid_ok:
            report += f"\n\n### TSVALID report\n\nFor more information see [tsvalid documentation](https://ontodev.github.io/tsvalid/checks.html)\n\n{tsvalid_report}"

    return report.strip(), sssom_json, sssom_rdf, sssom_markdown


# Helper function for logging configuration
@contextmanager
def configure_logger(capture_stream):
    """Configure logger to write to a stream."""
    logger = logging.getLogger()
    log_handler = logging.StreamHandler(capture_stream)
    log_handler.setLevel(logging.DEBUG)
    log_handler.setFormatter(logging.Formatter("**%(levelname)s**: %(message)s"))
    logger.addHandler(log_handler)
    try:
        yield
    finally:
        log_handler.flush()  # Ensure everything is written to the stream
        logger.removeHandler(log_handler)


def _get_package_version(package_name):
    try:
        return version(package_name)
    except PackageNotFoundError:
        return f"{package_name} is not installed."


def add_example():
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
HP:0000260	Wide anterior fontanel	skos:exactMatch	MP:0000085	large anterior fontanelle	semapv:LexicalMatching
HP:0000375	Abnormal cochlea morphology	skos:exactMatch	MP:0000031	abnormal cochlea morphology	semapv:LexicalMatching
HP:0000411	Protruding ear	skos:exactMatch	MP:0000021	prominent ears	semapv:LexicalMatching
HP:0000822	Hypertension	skos:exactMatch	MP:0000231	hypertension	semapv:LexicalMatching"""
    return example


limit_lines_evaluated = 1000
limit_lines_displayed = 5
st.image("src/sssom_validate_ui/resources/sssom-logo.png", use_container_width=True)
st.title("SSSOM Validator")

st.markdown(
    "This validator is provided by the [Monarch Initiative](https://monarchinitiative.org/)."
)
st.markdown(
    f"Currently, the validator checks the the first {limit_lines_evaluated} lines of the provided SSSOM file."
)

area_txt = "Paste your SSSOM mapping text here:"

result = add_example()
sssom_text = st.text_area(area_txt, result, height=400, key="sssom_input")

sssom_length_within_limit = True
if len(sssom_text.splitlines()) > limit_lines_evaluated:
    truncated_text = "\n".join(sssom_text.splitlines()[:limit_lines_evaluated])
    sssom_length_within_limit = False

if st.button("Validate"):
    if not sssom_length_within_limit:
        st.markdown(
            f"**Warning**: your file is too long, only the first {limit_lines_evaluated} lines will be evaluated."
        )

    result, sssom_json, sssom_rdf, sssom_markdown = validate_sssom(
        sssom_text, limit_lines_displayed
    )

    st.markdown(str(result).replace("\n", "\n\n"))

    rendering_text = f"""\n\n
### SSSOM Rendered\n\n"

This is how the first {limit_lines_displayed} lines of your SSSOM file look like when rendered in various formats.
"""

    st.markdown(sssom_markdown)

    if sssom_rdf:
        with st.expander("RDF"):
            rendering_text_rdf = f"""\n\n
        ```turtle
        {sssom_rdf}
        ```"""
            st.markdown(rendering_text_rdf)
    else:
        st.markdown(
            "Extension definitions are not supported in RDF output yet.\n"
            "Follow https://github.com/linkml/linkml/issues/2445 for updates."
        )

    with st.expander("JSON"):
        st.json(sssom_json)

tool_versions = f"""\n\n

### Validation info report

**sssom-py** version: {_get_package_version("sssom")}\n
**tsvalid** version: {_get_package_version("tsvalid")}\n
**linkml** version: {_get_package_version("linkml")}\n
"""
st.markdown(tool_versions)
