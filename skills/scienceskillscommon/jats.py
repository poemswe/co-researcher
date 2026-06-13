# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""JATS XML to markdown extraction shared by literature-review scripts."""

import re
import xml.etree.ElementTree as ET


def extract_all_text(elem):
  """Recursively extract all text content from an XML element."""
  parts = []
  if elem.text:
    parts.append(elem.text)
  for child in elem:
    parts.append(extract_all_text(child))
    if child.tail:
      parts.append(child.tail)
  return "".join(parts)


def xml_to_markdown(xml_string):
  """Extract article title, abstract, and body text from JATS XML."""
  try:
    root = ET.fromstring(xml_string)
  except ET.ParseError:
    text = re.sub(r"<[^>]*>?", " ", xml_string)
    return re.sub(r"\s+", " ", text).strip()

  sections = []

  for title in root.iter("article-title"):
    t = extract_all_text(title).strip()
    if t:
      sections.append(f"# {t}")
    break

  for abstract in root.iter("abstract"):
    text = extract_all_text(abstract).strip()
    if text:
      sections.append(f"## Abstract\n\n{text}")

  for body in root.iter("body"):
    body_parts = []
    for elem in body.iter():
      tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
      if tag == "title":
        title_text = extract_all_text(elem).strip()
        if title_text:
          body_parts.append(f"\n## {title_text}\n")
      elif tag == "p":
        para = extract_all_text(elem).strip()
        if para:
          body_parts.append(para)
    if body_parts:
      sections.append("\n\n".join(body_parts))
    break

  return "\n\n".join(sections)
