"""Simple streamlit app for validating SSSOM files."""

import logging
import sys
from io import StringIO

import pandas as pd
import requests
import streamlit as st

from sssom_validate_ui.utils import SSSOMValidation, generate_example, get_package_version

sys.tracebacklimit = 0


def _maybe_prune_sssom_text(sssom_text, limit_lines_evaluated):
    sssom_length_within_limit = True
    if len(sssom_text.splitlines()) > limit_lines_evaluated:
        truncated_text = "\n".join(sssom_text.splitlines()[:limit_lines_evaluated])
        sssom_length_within_limit = False
    else:
        truncated_text = sssom_text

    if not sssom_length_within_limit:
        logging.warning(
            f"Your file is too long, only the first {limit_lines_evaluated} lines will be evaluated."
        )
    return truncated_text


def _get_sssom_text(sssom_text_str, sssom_url_str, limit_lines_evaluated):
    """Get the SSSOM text from a string or URL. URL takes precedence.

    Args:
        sssom_text_str (str): The SSSOM text.
        sssom_url_str (str): The SSSOM URL.
        limit_lines_evaluated (int): The maximum number of lines to evaluate.

    Returns:
        StringIO: The SSSOM text as a StringIO object.

    Raises:
        ValueError: If the denominator is zero.
    """
    if sssom_text_str and sssom_url_str:
        logging.warning("Both SSSOM text and URL provided. URL will be used.")
    sssom_text = ""
    if sssom_text_str:
        sssom_text = sssom_text_str
    elif sssom_url_str:
        sssom_text = requests.get(sssom_url_str, timeout=60).text
    else:
        raise ValueError("No SSSOM text or URL provided.")
    return StringIO(_maybe_prune_sssom_text(sssom_text, limit_lines_evaluated))


def _validate_sssom(sssom_text: str, limit_lines_displayed=5):
    """Validate a mapping set using SSSOM and tsvalid validations."""
    pd.set_option("future.no_silent_downcasting", True)
    result = SSSOMValidation(sssom_text=sssom_text, limit_lines_displayed=limit_lines_displayed)
    result.run()
    return result


def _render_serialisation_section(serialisation_text, serialisation_format, markdown_type):
    if serialisation_text:
        with st.expander(serialisation_format):
            rendering_text_rdf = f"""\n\n
```{markdown_type}
{serialisation_text}
```"""
            st.markdown(rendering_text_rdf)
    else:
        st.markdown(f"{serialisation_format} rendering is not available for this file, see log.")


def _render_validation_badge(valid: bool, key: str):
    if valid:
        badge_url = f"https://img.shields.io/badge/{key}-SUCCESSFUL-green?style=green"
    else:
        badge_url = f"https://img.shields.io/badge/{key}-UNSUCCESSFUL-red?style=flat"

    st.markdown(f"![Badge]({badge_url})")


def _render_tool_information():
    tool_versions = f"""\n\n

### Validation info report

**sssom-py** version: {get_package_version("sssom")}\n
**tsvalid** version: {get_package_version("tsvalid")}\n
**linkml** version: {get_package_version("linkml")}\n
"""
    st.markdown(tool_versions)


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

sssom_text = st.text_area(area_txt, generate_example(), height=400, key="sssom_input")
example_url = ""
sssom_url_input = st.text_input(
    "Paste a URL to your SSSOM file here.", example_url, key="sssom_input_url"
)

if st.button("Validate"):
    sssom_text = _get_sssom_text(sssom_text, sssom_url_input, limit_lines_evaluated)
    result: SSSOMValidation = _validate_sssom(sssom_text, limit_lines_displayed)

    _render_validation_badge(result.is_valid(), "Validation%20status%20overall")

    st.header("tsvalid validation")
    _render_validation_badge(result.is_ok_tsvalid(), "tsvalid")
    st.markdown(
        "For more information see [tsvalid documentation](https://ontodev.github.io/tsvalid/checks.html)"
    )
    with st.expander("Report"):
        st.markdown(result.get_tsvalid_report())

    st.header("SSSOM Schema validation")
    _render_validation_badge(result.is_ok_sssom_validation(), "SSSOM")
    st.markdown(
        "For more information see [SSSOM documentation](https://mapping-commons.github.io/sssom/linkml-index/)"
    )
    with st.expander("Report"):
        st.markdown(result.get_sssom_validation_report())

    st.header("SSSOM Sample Conversions")
    _render_validation_badge(result.is_ok_sssom_conversion(), "SSSOM")
    st.markdown(
        "This is how the first {limit_lines_displayed} lines of your SSSOM file look like when rendered in various formats."
    )
    st.markdown(
        "For more information see [SSSOM documentation](https://mapping-commons.github.io/sssom/spec-formats/)"
    )
    st.markdown(result.sssom_markdown)
    with st.expander("Conversion report"):
        st.markdown(result.get_sssom_conversion_report())
    _render_serialisation_section(result.sssom_rdf, "RDF", "turtle")
    _render_serialisation_section(result.sssom_json, "JSON", "json")

st.header("Additional information")
_render_tool_information()

st.header("Contact")
st.image("src/sssom_validate_ui/resources/monarch.png", use_container_width=False, width=300)
st.markdown("Presented by the [Monarch Initiative](https://monarchinitiative.org/)")
st.markdown(
    "For feedback use our [issue tracker](https://github.com/mapping-commons/sssom-validate-ui)."
)
