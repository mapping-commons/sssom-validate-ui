import logging
import re
from io import StringIO
from pathlib import Path
from typing import Any, Dict, Optional, Union
from urllib.request import urlopen
import sys

sys.tracebacklimit = 0
from contextlib import redirect_stdout, redirect_stderr

import pandas as pd
import streamlit as st
import validators
import yaml
from sssom.constants import (
    CURIE_MAP,
)
from sssom.parsers import _get_prefix_map_and_metadata, from_sssom_dataframe
from sssom.typehints import MetadataType, PrefixMap
from sssom.util import (
    MappingSetDataFrame,
    sort_df_rows_columns,
)
from sssom.constants import SchemaValidationType
from sssom.validators import validate

# Move this to sssom-py
def _read_metadata_from_table(path: Union[str, Path, StringIO]) -> Dict[str, Any]:
    if isinstance(path, Path) and not isinstance(path, StringIO) or not isinstance(path, StringIO) and not validators.url(path):
        with open(path) as file:
            yamlstr = ""
            for line in file:
                if line.startswith("#"):
                    yamlstr += re.sub("^#", "", line)
                else:
                    break
    if isinstance(path, StringIO) or not validators.url(path):
        yamlstr = ""
        for line in path:
            if line.startswith("#"):
                yamlstr += re.sub("^#", "", line)
            else:
                break
    else:
        response = urlopen(path)
        yamlstr = ""
        for lin in response:
            line = lin.decode("utf-8")
            if line.startswith("#"):
                yamlstr += re.sub("^#", "", line)
            else:
                break

    if yamlstr:
        meta = yaml.safe_load(yamlstr)
        logging.info(f"Meta={meta}")
        return meta
    return {}

# move this to sssom-py
def parse_sssom_table_from_string(
    data: str,
    prefix_map: Optional[PrefixMap] = None,
    meta: Optional[MetadataType] = None,
    **kwargs
    # mapping_predicates: Optional[List[str]] = None,
) -> MappingSetDataFrame:
    """Parse a TSV to a :class:`MappingSetDocument` to a :class:`MappingSetDataFrame`."""
    #raise_for_bad_path(file_path)
    #
    data_io = StringIO(data)
    sep = "\t"
    #df = read_pandas(data_io)
   # df = pd.read_csv(data_io, comment='#')
    df = pd.read_csv(data_io, sep=sep, low_memory=False, comment='#').fillna("")
    df = sort_df_rows_columns(df)

    # if mapping_predicates:
    #     # Filter rows based on presence of predicate_id list provided.
    #     df = df[df["predicate_id"].isin(mapping_predicates)]

    # If SSSOM external metadata is provided, merge it with the internal metadata
    sssom_metadata = _read_metadata_from_table(data_io)

    if sssom_metadata:
        if meta:
            for k, v in meta.items():
                if k in sssom_metadata:
                    if sssom_metadata[k] != v:
                        logging.warning(
                            f"SSSOM internal metadata {k} ({sssom_metadata[k]}) "
                            f"conflicts with provided ({meta[k]})."
                        )
                else:
                    logging.info(
                        f"Externally provided metadata {k}:{v} is added to metadata set."
                    )
                    sssom_metadata[k] = v
        meta = sssom_metadata

        if "curie_map" in sssom_metadata:
            if prefix_map:
                for k, v in prefix_map.items():
                    if k in sssom_metadata[CURIE_MAP]:
                        if sssom_metadata[CURIE_MAP][k] != v:
                            logging.warning(
                                f"SSSOM prefix map {k} ({sssom_metadata[CURIE_MAP][k]}) "
                                f"conflicts with provided ({prefix_map[k]})."
                            )
                    else:
                        logging.info(
                            f"Externally provided metadata {k}:{v} is added to metadata set."
                        )
                        sssom_metadata[CURIE_MAP][k] = v
            prefix_map = sssom_metadata[CURIE_MAP]

    meta_all = _get_prefix_map_and_metadata(prefix_map=prefix_map, meta=meta)
    msdf = from_sssom_dataframe(
        df, prefix_map=meta_all.prefix_map, meta=meta_all.metadata
    )
    return msdf

def validate_sssom(sssom_text):
    validation_types = [SchemaValidationType.JsonSchema]
    msdf = parse_sssom_table_from_string(data=sssom_text)
    
    try:
        validate(msdf=msdf, validation_types=validation_types)
    except Exception as e:
        return str(e)

    return "All good."



st.title('SSSOM Validator')

# 1. textarea for pasting chunks of a file
sssom_text = st.text_area('Paste your SSSOM mapping text here:', '')

# 2. validate button
if st.button('Validate'):
    # when the validate button is clicked a method is executed 
    # that reads the text from the text area, 
    # and prints the number of characters to the second text area.
    result = validate_sssom(sssom_text)

    # 3. textarea to print results
    st.text_area('Result:', str(result))
