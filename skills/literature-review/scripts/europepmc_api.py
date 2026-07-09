# MIT License
#
# Copyright (c) 2026 Poe Poe / co-researcher contributors
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT
# WARRANTY OF ANY KIND. See the MIT License for details.
#
# Original to this repository. Wraps the public Europe PMC REST API; design
# inspired by google-deepmind/science-skills, no code copied.

"""Europe PMC API CLI — search, full text, PDF, citations, references.

Usage:
  uv run europepmc_api.py search "CRISPR" --max_results 5 --output out.json
  uv run europepmc_api.py get_fulltext PMC8371605 --output ft.txt
"""

# /// script
# requires-python = ">=3.10"
# ///

import argparse
import json
import os
import sys
import urllib.parse

import http_client
import jats

_API_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/"
_PDF_BASE = "https://europepmc.org/"
_REFERER = "literature-search-europepmc"

_API_CLIENT = http_client.HttpClient(_API_BASE, qps=1.0, referer_skill=_REFERER)
_PDF_CLIENT = http_client.HttpClient(_PDF_BASE, qps=1.0, referer_skill=_REFERER)


def write_output(data, output_file, *, as_json=True) -> None:
  try:
    with open(output_file, "w", encoding="utf-8") as handle:
      if as_json:
        json.dump(data, handle, indent=2)
      else:
        handle.write(data)
  except (OSError, TypeError) as err:
    sys.exit(f"Error writing to file {output_file}: {err}")
  print(f"Success! Data written to: {output_file}")


def search(query, max_results=10, result_type="core", cursor="*", sort=""):
  """Search Europe PMC (open access only) and return article metadata."""
  if "OPEN_ACCESS:" not in query.upper():
    query = f"({query}) AND OPEN_ACCESS:y"
  params = {
      "query": query,
      "format": "json",
      "resultType": result_type,
      "pageSize": min(max_results, 1000),
      "cursorMark": cursor,
  }
  if sort:
    params["sort"] = sort

  print(f"Searching Europe PMC (open access): {query}", file=sys.stderr)
  data = _API_CLIENT.fetch_json(f"search?{urllib.parse.urlencode(params)}")
  results = data.get("resultList", {}).get("result", [])[:max_results]
  hit_count = data.get("hitCount", 0)
  next_cursor = data.get("nextCursorMark", "")
  print(f"Europe PMC: {hit_count} total hits ({len(results)} returned)",
        file=sys.stderr)
  return {
      "hitCount": hit_count,
      "nextCursorMark": next_cursor if next_cursor != cursor else "",
      "results": results,
  }


def download_pdf(pmcid, output) -> None:
  """Download an open-access PDF by PMCID."""
  print(f"Downloading PDF for {pmcid}...", file=sys.stderr)
  content = _PDF_CLIENT.fetch_bytes(f"articles/{pmcid}?pdf=render", timeout=60)
  if not content.startswith(b"%PDF"):
    sys.exit(f"Error: response for {pmcid} is not a PDF (not open access?).")
  out_dir = os.path.dirname(output)
  if out_dir:
    os.makedirs(out_dir, exist_ok=True)
  with open(output, "wb") as handle:
    handle.write(content)
  print(f"Saved {len(content)} bytes to {output}", file=sys.stderr)


def get_fulltext(pmcid, fmt="text"):
  """Retrieve open-access full text by PMCID as raw XML or markdown."""
  print(f"Fetching full text for {pmcid}...", file=sys.stderr)
  xml = _API_CLIENT.fetch_text(f"{pmcid}/fullTextXML", timeout=60)
  return xml if fmt == "xml" else jats.xml_to_markdown(xml)


def _paged_list(source, article_id, kind, result_key, item_key, page, page_size):
  params = urllib.parse.urlencode({
      "page": page,
      "pageSize": min(page_size, 1000),
      "format": "json",
  })
  print(f"Fetching {kind} for {source}/{article_id}...", file=sys.stderr)
  data = _API_CLIENT.fetch_json(f"{source}/{article_id}/{kind}?{params}")
  items = data.get(result_key, {}).get(item_key, [])
  return {"hitCount": data.get("hitCount", 0), kind: items}


def get_citations(source, article_id, page=1, page_size=25):
  """Retrieve articles citing a paper."""
  return _paged_list(source, article_id, "citations", "citationList",
                     "citation", page, page_size)


def get_references(source, article_id, page=1, page_size=25):
  """Retrieve a paper's reference list."""
  return _paged_list(source, article_id, "references", "referenceList",
                     "reference", page, page_size)


def _build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(
      description="Europe PMC API: search, full text, PDF, citations, refs.")
  sub = parser.add_subparsers(dest="command", required=True)

  p = sub.add_parser("search", help="Search Europe PMC")
  p.add_argument("query")
  p.add_argument("--max_results", type=int, default=10)
  p.add_argument("--result_type", default="core", choices=["core", "lite"])
  p.add_argument("--cursor", default="*", help="Cursor mark for pagination")
  p.add_argument("--sort", default="", help="e.g. 'CITED desc'")
  p.add_argument("--output", required=True)

  p = sub.add_parser("download_pdf", help="Download PDF by PMCID")
  p.add_argument("pmcid")
  p.add_argument("--output", required=True)

  p = sub.add_parser("get_fulltext", help="Retrieve full text by PMCID")
  p.add_argument("pmcid")
  p.add_argument("--format", dest="fmt", default="text",
                 choices=["text", "xml"])
  p.add_argument("--output", required=True)

  for name, label in (("get_citations", "citing articles"),
                      ("get_references", "reference list")):
    p = sub.add_parser(name, help=f"Get {label} of a paper")
    p.add_argument("source", help="Source DB (MED, PMC, PPR)")
    p.add_argument("article_id", help="PMID or PMCID")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--page_size", type=int, default=25)
    p.add_argument("--output", required=True)

  return parser


def main() -> None:
  args = _build_parser().parse_args()

  if args.command == "search":
    result = search(args.query, args.max_results, args.result_type,
                    args.cursor, args.sort)
    write_output(result, args.output)
    if result["nextCursorMark"]:
      print(f"Next cursor: {result['nextCursorMark']}", file=sys.stderr)
  elif args.command == "download_pdf":
    download_pdf(args.pmcid, args.output)
  elif args.command == "get_fulltext":
    write_output(get_fulltext(args.pmcid, args.fmt), args.output, as_json=False)
  elif args.command == "get_citations":
    write_output(
        get_citations(args.source, args.article_id, args.page, args.page_size),
        args.output)
  elif args.command == "get_references":
    write_output(
        get_references(args.source, args.article_id, args.page, args.page_size),
        args.output)


if __name__ == "__main__":
  main()
