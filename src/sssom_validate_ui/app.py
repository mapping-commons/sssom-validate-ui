"""Simple streamlit app for validating SSSOM files."""

import sys
from io import StringIO
from typing import List

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


def validate_sssom(sssom_text_str):
    """Validate mapping set using the standard SSSOM methods."""
    validation_types = [
        SchemaValidationType.JsonSchema,
        SchemaValidationType.PrefixMapCompleteness,
    ]
    data_io = StringIO(sssom_text_str)
    msdf = parse_sssom_table(data_io)

    report = ""

    sssom_reports: List[ValidationReport] = validate(msdf=msdf, validation_types=validation_types)
    tsvalid_report = validates(stream=data_io, exceptions=["E9"], summary=True, fail=False)
    linkml_report = validate_linkml(msdf=msdf)

    report += "SSSOM report"
    for r in sssom_reports.results:
        report += r
    report += "TSVALID report"
    report += str(tsvalid_report)
    report += "LinkML report"
    report += str(linkml_report)

    return report if report else "All Good"


def add_example():
    """Add an example to the input text area."""
    example = """# curie_map:
#   HP: http://purl.obolibrary.org/obo/HP_
#   MP: http://purl.obolibrary.org/obo/MP_
#   owl: http://www.w3.org/2002/07/owl#
#   rdf: http://www.w3.org/1999/02/22-rdf-syntax-ns#
#   rdfs: http://www.w3.org/2000/01/rdf-schema#
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


st.title("SSSOM Validator")

area_txt = "Paste your SSSOM mapping text here:"

result = add_example()
# 1. textarea for pasting chunks of a file
sssom_text = st.text_area(area_txt, result, key="sssom_input")

# 2. validate button
if st.button("Validate"):
    # when the validate button is clicked a method is executed
    # that reads the text from the text area,
    # and prints the number of characters to the second text area.
    result = validate_sssom(sssom_text)

    # 3. textarea to print results
    st.text_area("Result:", str(result))
