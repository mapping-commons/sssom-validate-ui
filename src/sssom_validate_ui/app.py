"""Simple streamlit app for validating SSSOM files."""

import sys
from io import StringIO
from typing import List
from contextlib import redirect_stdout, redirect_stderr, contextmanager
import logging
from importlib.metadata import version, PackageNotFoundError



import streamlit as st
from linkml.generators.pythongen import PythonGenerator
from linkml.validators.jsonschemavalidator import JsonSchemaDataValidator
from sssom.constants import SCHEMA_YAML, SchemaValidationType
from sssom.parsers import parse_sssom_table, to_mapping_set_document
from sssom.util import MappingSetDataFrame
from sssom.validators import ValidationReport, validate
from tsvalid.tsvalid import validates

sys.tracebacklimit = 0


def validate_linkml(msdf: MappingSetDataFrame):
    """Validate the contents of the mapping set using the LinkML JSON Schema validator."""
    mod = PythonGenerator(SCHEMA_YAML).compile_module()
    validator = JsonSchemaDataValidator(schema=SCHEMA_YAML)

    mapping_set = to_mapping_set_document(msdf).mapping_set
    result = validator.validate_object(mapping_set, target_class=mod.MappingSet)
    return result


import logging
import sys
from io import StringIO
import pandas as pd
from contextlib import redirect_stdout, redirect_stderr

def validate_sssom(sssom_text_str):
    """Validate a mapping set using SSSOM and tsvalid validations."""
    
    # Capture logs for SSSOM validation
    sssom_validation_capture = StringIO()
    sssom_text = StringIO(sssom_text_str)
    pd.set_option('future.no_silent_downcasting', True)
    with redirect_stdout(sssom_validation_capture), redirect_stderr(sssom_validation_capture), configure_logger(sssom_validation_capture):
        validation_types = [
            SchemaValidationType.JsonSchema,
            SchemaValidationType.PrefixMapCompleteness,
            SchemaValidationType.StrictCurieFormat,
        ]
        msdf = parse_sssom_table(sssom_text)
        validate(msdf=msdf, validation_types=validation_types, fail_on_error=False)
    log_output = sssom_validation_capture.getvalue() or "No validation issues detected."
    sssom_ok = "No validation issues detected." in log_output

    # Capture logs for tsvalid validation
    tsvalid_capture = StringIO()
    with redirect_stdout(tsvalid_capture), redirect_stderr(tsvalid_capture), configure_logger(tsvalid_capture):
        validates(sssom_text, comment="#", exceptions=[], summary=True, fail=False)

    # Restore outputs and get results
    tsvalid_report = tsvalid_capture.getvalue() or "No validation issues detected."
    tsvalid_ok = "No validation issues detected." in tsvalid_report
    # Compile the validation report
    
    report = ""
    
    if sssom_ok and tsvalid_ok:
        report = "No validation issues detected."
    else:
        report = f"Some problems where found with your file."
        if not sssom_ok:
            report += f"\n\n### SSSOM report\n\nFor more information see [SSSOM documentation](https://mapping-commons.github.io/sssom/linkml-index/)\n\n{log_output}"
        if not tsvalid_ok:
            report += f"\n\n### TSVALID report\n\nFor more information see [tsvalid documentation](https://ontodev.github.io/tsvalid/checks.html)\n\n{tsvalid_report}"
    
    report += f"""\n\n

### Validation info report

sssom-py version: {get_package_version("sssom")}
tsvalid version: {get_package_version("tsvalid")}
linkml version: {get_package_version("linkml")}
"""
    return report.strip()


# Helper function for logging configuration
@contextmanager
def configure_logger(capture_stream):
    """Configure logger to write to a stream."""
    logger = logging.getLogger()
    log_handler = logging.StreamHandler(capture_stream)
    log_handler.setLevel(logging.DEBUG)
    log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(log_handler)
    try:
        yield
    finally:
        log_handler.flush()  # Ensure everything is written to the stream
        logger.removeHandler(log_handler)

def get_package_version(package_name):
    try:
        return version(package_name)
    except PackageNotFoundError:
       return (f"{package_name} is not installed.")


# Example usage
if __name__ == "__main__":
    sssom_text = """subject_id\tpredicate_id\tobject_id\nEX:001\tEX:relatedTo\tEX:002"""
    print(validate_sssom(sssom_text))



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
st.image("src/sssom_validate_ui/resources/sssom-logo.png", use_container_width=True)
st.title("SSSOM Validator")

st.markdown("This validator is provided by the [Monarch Initiative](https://monarchinitiative.org/).")
st.markdown(f"Currently, the validator checks the the first {limit_lines_evaluated} lines of the provided SSSOM file.")

area_txt = "Paste your SSSOM mapping text here:"

result = add_example()
sssom_text = st.text_area(area_txt, result, height=400, key="sssom_input")

sssom_length_within_limit = True
if len(sssom_text.splitlines())>limit_lines_evaluated:
    truncated_text = "\n".join(sssom_text.splitlines()[:limit_lines_evaluated])
    sssom_length_within_limit = False
    
if st.button("Validate"):
    if not sssom_length_within_limit:
         st.markdown(f"**Warning**: your file is too long, only the first {limit_lines_evaluated} lines will be evaluated.")
    
    result = validate_sssom(sssom_text)

    # 3. textarea to print results
    st.markdown(str(result).replace("\n", "\n\n"))
