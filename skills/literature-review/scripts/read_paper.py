"""Unified full-text acquisition for a paper given a DOI, arXiv ID, or PMCID.

Resolution chain: cached/user files, Europe PMC JATS, arXiv PDF,
OpenAlex best_oa_location PDF, OpenAlex abstract fallback.
Prints exactly one JSON status line to stdout:
  {"status": "fulltext|abstract-only", "path": ..., "source": ..., "id": ...}
Paywalled papers are a normal outcome (abstract-only), not an error.
"""

# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "scienceskillscommon",
#   "pymupdf4llm",
# ]
# [tool.uv.sources]
# scienceskillscommon = { path = "../../scienceskillscommon" }
# ///

import argparse
import json
import os
import pathlib
import re
import sys
import urllib.parse

import pymupdf4llm

from science_skills.scienceskillscommon import http_client, jats

_OPENALEX = http_client.HttpClient("https://api.openalex.org/", qps=1.0)
_EPMC = http_client.HttpClient(
    "https://www.ebi.ac.uk/europepmc/webservices/rest/",
    qps=1.0,
    referer_skill="literature-search-europepmc",
)
_ARXIV = http_client.HttpClient("https://arxiv.org/", qps=1.0 / 3.0)


def sanitize_id(identifier: str) -> str:
  return re.sub(r"[^A-Za-z0-9._-]", "_", identifier)


def doi_to_arxiv(doi: str) -> str | None:
  prefix = "10.48550/arxiv."
  if doi.lower().startswith(prefix):
    return doi[len(prefix):]
  return None


def abstract_from_inverted_index(inv: dict) -> str:
  positions = sorted((p, w) for w, ps in inv.items() for p in ps)
  return " ".join(w for _, w in positions)


def pmcid_from_ids(ids: dict) -> str | None:
  raw = ids.get("pmcid") or ""
  match = re.search(r"PMC\d+", raw)
  return match.group(0) if match else None


def emit(status: str, path, source: str, identifier: str) -> None:
  print(json.dumps({
      "status": status,
      "path": str(path) if path else None,
      "source": source,
      "id": identifier,
  }))
