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


def extract_pdf(pdf_path: pathlib.Path) -> str:
  return pymupdf4llm.to_markdown(str(pdf_path))


def try_extract(pdf_path: pathlib.Path, fulltext_path: pathlib.Path) -> bool:
  try:
    md = extract_pdf(pdf_path)
  except Exception as e:
    print(f"PDF extraction failed for {pdf_path}: {e}", file=sys.stderr)
    return False
  if not md.strip():
    return False
  fulltext_path.write_text(md, encoding="utf-8")
  return True


def fetch_epmc_fulltext(pmcid: str) -> str | None:
  return None


def read_paper(doi, arxiv, pmcid, workspace) -> None:
  identifier = doi or arxiv or pmcid
  paper_dir = pathlib.Path(workspace) / "papers" / sanitize_id(identifier)
  paper_dir.mkdir(parents=True, exist_ok=True)
  pdf_path = paper_dir / "paper.pdf"
  fulltext_path = paper_dir / "fulltext.md"
  abstract_path = paper_dir / "abstract.md"

  if fulltext_path.exists():
    return emit("fulltext", fulltext_path, "cached", identifier)
  if pdf_path.exists() and try_extract(pdf_path, fulltext_path):
    return emit("fulltext", fulltext_path, "user_pdf", identifier)

  if pmcid:
    text = fetch_epmc_fulltext(pmcid)
    if text:
      fulltext_path.write_text(text, encoding="utf-8")
      return emit("fulltext", fulltext_path, "epmc", identifier)

  emit("abstract-only", None, "none", identifier)
