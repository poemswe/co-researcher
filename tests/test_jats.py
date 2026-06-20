# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pytest",
# ]
# ///

import pathlib
import sys

import pytest

sys.path.insert(0, str(
    pathlib.Path(__file__).resolve().parent.parent
    / "skills/literature-review/scripts"))
import jats

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


_JATS_NS_SAMPLE = """<?xml version="1.0"?>
<article xmlns="http://jats.nlm.nih.gov">
  <front><article-meta>
    <title-group><article-title>NS Paper</article-title></title-group>
    <abstract><p>NS abstract.</p></abstract>
  </article-meta></front>
  <body><sec><title>Intro</title><p>NS body text.</p></sec></body>
</article>
"""


def test_xml_to_markdown_handles_namespaced_jats():
  md = jats.xml_to_markdown(_JATS_NS_SAMPLE)
  assert "# NS Paper" in md
  assert "## Abstract" in md
  assert "NS abstract." in md
  assert "## Intro" in md
  assert "NS body text." in md


def test_xml_to_markdown_falls_back_on_invalid_xml():
  md = jats.xml_to_markdown("<broken><xml")
  assert "<" not in md


def test_extract_all_text_flattens_nested_markup():
  import xml.etree.ElementTree as ET
  elem = ET.fromstring("<p>alpha <b>beta</b> gamma</p>")
  assert jats.extract_all_text(elem) == "alpha beta gamma"


if __name__ == "__main__":
  sys.exit(pytest.main([__file__, "-v"]))
