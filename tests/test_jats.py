# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pytest",
#   "scienceskillscommon",
# ]
# [tool.uv.sources]
# scienceskillscommon = { path = "../skills/scienceskillscommon" }
# ///

import sys

import pytest

from science_skills.scienceskillscommon import jats

_JATS_SAMPLE = """<?xml version="1.0"?>
<article>
  <front><article-meta>
    <title-group><article-title>Test <italic>Paper</italic></article-title></title-group>
    <abstract><p>An abstract sentence.</p></abstract>
  </article-meta></front>
  <body>
    <sec><title>Methods</title><p>We did things.</p></sec>
    <sec><title>Results</title><p>Things happened.</p></sec>
  </body>
</article>
"""


def test_xml_to_markdown_extracts_title_abstract_body():
  md = jats.xml_to_markdown(_JATS_SAMPLE)
  assert "# Test Paper" in md
  assert "## Abstract" in md
  assert "An abstract sentence." in md
  assert "## Methods" in md
  assert "We did things." in md
  assert "## Results" in md


def test_xml_to_markdown_falls_back_on_invalid_xml():
  md = jats.xml_to_markdown("<broken><xml")
  assert "<" not in md


def test_extract_all_text_flattens_nested_markup():
  import xml.etree.ElementTree as ET
  elem = ET.fromstring("<p>alpha <b>beta</b> gamma</p>")
  assert jats.extract_all_text(elem) == "alpha beta gamma"


if __name__ == "__main__":
  sys.exit(pytest.main([__file__, "-v"]))
