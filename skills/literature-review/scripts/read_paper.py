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

# Must precede the pymupdf4llm import: stops PyMuPDF printing its layout
# recommendation to stdout, which would corrupt our JSON status line.
os.environ.setdefault("PYMUPDF_SUGGEST_LAYOUT_ANALYZER", "0")

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


def lookup_openalex_work(doi: str) -> dict | None:
  url = f"https://api.openalex.org/works/https://doi.org/{doi}"
  api_key = os.environ.get("OPENALEX_API_KEY")
  if api_key:
    url += "?" + urllib.parse.urlencode({"api_key": api_key})
  try:
    return _OPENALEX.fetch_json(url)
  except http_client.HttpError as e:
    if e.status_code != 404:
      print(f"OpenAlex lookup failed for {doi}: {e}", file=sys.stderr)
    return None


def resolve_pmcid_via_epmc(doi: str) -> str | None:
  params = urllib.parse.urlencode({
      "query": f'DOI:"{doi}"',
      "format": "json",
      "resultType": "lite",
      "pageSize": 1,
  })
  try:
    data = _EPMC.fetch_json(f"search?{params}")
  except http_client.HttpError:
    return None
  for result in data.get("resultList", {}).get("result", []):
    if pmcid := result.get("pmcid"):
      return pmcid
  return None


def fetch_epmc_fulltext(pmcid: str) -> str | None:
  try:
    xml = _EPMC.fetch_text(f"{pmcid}/fullTextXML", timeout=60)
  except http_client.HttpError:
    return None
  md = jats.xml_to_markdown(xml)
  return md if md.strip() else None


def _download_pdf(client, url: str, dest: pathlib.Path, timeout: int) -> bool:
  try:
    data = client.fetch_bytes(url, timeout=timeout)
  except http_client.HttpError:
    return False
  if data[:5] != b"%PDF-":
    return False
  dest.write_bytes(data)
  return True


def fetch_arxiv_pdf(arxiv_id: str, dest: pathlib.Path) -> bool:
  return _download_pdf(
      _ARXIV, f"https://arxiv.org/pdf/{arxiv_id}.pdf", dest, timeout=60)


def fetch_oa_pdf(url: str, dest: pathlib.Path) -> bool:
  parsed = urllib.parse.urlparse(url)
  if parsed.scheme not in ("http", "https") or not parsed.netloc:
    return False
  client = http_client.HttpClient(f"{parsed.scheme}://{parsed.netloc}", qps=1.0)
  return _download_pdf(client, url, dest, timeout=120)


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

  work = (lookup_openalex_work(doi) if doi else None) or {}
  pmcid = pmcid or pmcid_from_ids(work.get("ids") or {})
  if not pmcid and doi:
    pmcid = resolve_pmcid_via_epmc(doi)
  arxiv = arxiv or (doi_to_arxiv(doi) if doi else None)

  if pmcid:
    text = fetch_epmc_fulltext(pmcid)
    if text:
      fulltext_path.write_text(text, encoding="utf-8")
      return emit("fulltext", fulltext_path, "epmc", identifier)

  if arxiv and fetch_arxiv_pdf(arxiv, pdf_path):
    if try_extract(pdf_path, fulltext_path):
      return emit("fulltext", fulltext_path, "arxiv_pdf", identifier)

  oa = work.get("best_oa_location") or {}
  if oa.get("pdf_url") and fetch_oa_pdf(oa["pdf_url"], pdf_path):
    if try_extract(pdf_path, fulltext_path):
      return emit("fulltext", fulltext_path, "oa_pdf", identifier)

  inv = work.get("abstract_inverted_index")
  if inv:
    title = work.get("title") or identifier
    abstract_path.write_text(
        f"# {title}\n\n{abstract_from_inverted_index(inv)}\n",
        encoding="utf-8",
    )
    return emit("abstract-only", abstract_path, "openalex_abstract", identifier)

  emit("abstract-only", None, "none", identifier)


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(
      description="Acquire full text for a paper into papers/{id}/."
  )
  group = parser.add_mutually_exclusive_group(required=True)
  group.add_argument("--doi", help="DOI, e.g. 10.1038/s41586-021-03819-2")
  group.add_argument("--arxiv", help="arXiv ID, e.g. 1706.03762")
  group.add_argument("--pmcid", help="PubMed Central ID, e.g. PMC8371605")
  parser.add_argument(
      "--workspace", default=".",
      help="Parent directory of papers/ (default: current directory)",
  )
  return parser.parse_args()


if __name__ == "__main__":
  args = parse_args()
  read_paper(args.doi, args.arxiv, args.pmcid, args.workspace)
