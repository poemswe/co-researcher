# MIT License
#
# Copyright (c) 2026 Poe Poe / co-researcher contributors
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction. The above copyright notice and this
# permission notice shall be included in all copies. THE SOFTWARE IS PROVIDED
# "AS IS", WITHOUT WARRANTY OF ANY KIND. See the MIT License for details.
#
# Original to this repository.

"""Extract title, abstract, and body text from JATS XML as markdown."""

import re
import xml.etree.ElementTree as ET


def _local_name(tag):
  """Strip any XML namespace prefix from an element tag."""
  return tag.rpartition("}")[2]


def _iter_local(root, name):
  """Yield descendants whose namespace-stripped tag equals `name`."""
  for element in root.iter():
    if _local_name(element.tag) == name:
      yield element


def extract_all_text(elem):
  """Return all text under `elem`, flattening nested inline markup."""
  pieces = []
  if elem.text:
    pieces.append(elem.text)
  for child in elem:
    pieces.append(extract_all_text(child))
    if child.tail:
      pieces.append(child.tail)
  return "".join(pieces)


def xml_to_markdown(xml_string):
  """Convert a JATS article into a markdown title/abstract/body string.

  Falls back to a crude tag strip when the input is not well-formed XML.
  Namespace prefixes are ignored throughout, so namespaced JATS works too.
  """
  try:
    root = ET.fromstring(xml_string)
  except ET.ParseError:
    stripped = re.sub(r"<[^>]*>?", " ", xml_string)
    return re.sub(r"\s+", " ", stripped).strip()

  sections = []

  for title in _iter_local(root, "article-title"):
    text = extract_all_text(title).strip()
    if text:
      sections.append(f"# {text}")
    break

  for abstract in _iter_local(root, "abstract"):
    text = extract_all_text(abstract).strip()
    if text:
      sections.append(f"## Abstract\n\n{text}")

  for body in _iter_local(root, "body"):
    parts = []
    for element in body.iter():
      tag = _local_name(element.tag)
      if tag == "title":
        heading = extract_all_text(element).strip()
        if heading:
          parts.append(f"\n## {heading}\n")
      elif tag == "p":
        para = extract_all_text(element).strip()
        if para:
          parts.append(para)
    if parts:
      sections.append("\n\n".join(parts))
    break

  return "\n\n".join(sections)
