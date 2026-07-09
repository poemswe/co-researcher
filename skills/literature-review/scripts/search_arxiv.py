# MIT License
#
# Copyright (c) 2026 Poe Poe / co-researcher contributors
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT
# WARRANTY OF ANY KIND. See the MIT License for details.
#
# Original to this repository. Wraps the public arXiv Atom API; design inspired
# by google-deepmind/science-skills, no code copied.

"""Search the arXiv API and emit one clean JSON object.

Queries arXiv by search string or id list, parses the Atom feed, and prints
`{"status", "results_count", "papers": [...]}` to stdout (hit count to stderr).
"""

# /// script
# requires-python = ">=3.10"
# ///

import argparse
import json
import sys
import urllib.parse
import xml.etree.ElementTree as ET

import http_client

_BASE_URL = "http://export.arxiv.org/api/query?"
_ATOM = "{http://www.w3.org/2005/Atom}"
_CLIENT = http_client.HttpClient(_BASE_URL, qps=1.0 / 3.0)


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(
      description="Search arXiv API and return clean JSON")
  parser.add_argument("--query", type=str,
                      help="Search query, e.g. 'au:einstein AND ti:relativity'")
  parser.add_argument("--id_list", type=str,
                      help="Comma-separated list of arXiv IDs")
  parser.add_argument("--start", type=int, default=0, help="Pagination offset")
  parser.add_argument("--max_results", type=int, default=10,
                      help="Number of results to return")
  parser.add_argument("--sort_by", type=str,
                      choices=["relevance", "lastUpdatedDate", "submittedDate"],
                      help="Sort by")
  parser.add_argument("--sort_order", type=str,
                      choices=["ascending", "descending"], help="Sort order")
  return parser.parse_args()


def _text(entry, tag):
  node = entry.find(f"{_ATOM}{tag}")
  if node is None or node.text is None:
    return ""
  return " ".join(node.text.split())


def _parse_entry(entry) -> dict:
  paper = {}
  raw_id = _text(entry, "id")
  if raw_id:
    paper["id"] = raw_id.split("/abs/")[-1]
  for tag in ("title", "summary"):
    value = _text(entry, tag)
    if value:
      paper[tag] = value
  published = entry.find(f"{_ATOM}published")
  if published is not None:
    paper["published"] = published.text
  for link in entry.findall(f"{_ATOM}link"):
    if link.get("title") == "pdf":
      paper["pdf_url"] = link.get("href")
  category = entry.find(f"{_ATOM}primary_category")
  if category is not None:
    paper["primary_category"] = category.get("term")
  for extra in ("doi", "journal_ref", "comment"):
    node = entry.find(f"{_ATOM}{extra}")
    if node is not None:
      paper[extra] = node.text
  paper["authors"] = [
      name.text
      for author in entry.findall(f"{_ATOM}author")
      for name in author.findall(f"{_ATOM}name")
  ]
  return paper


def search_arxiv(args: argparse.Namespace) -> None:
  params = {"start": args.start, "max_results": args.max_results}
  if args.query:
    params["search_query"] = args.query
  if args.id_list:
    params["id_list"] = args.id_list
  if args.sort_by:
    params["sortBy"] = args.sort_by
  if args.sort_order:
    params["sortOrder"] = args.sort_order

  query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote_plus)
  root = ET.fromstring(_CLIENT.fetch_bytes(_BASE_URL + query))
  papers = [_parse_entry(entry) for entry in root.findall(f"{_ATOM}entry")]

  print(f"arXiv: {len(papers)} results", file=sys.stderr)
  print(json.dumps(
      {"status": "success", "results_count": len(papers), "papers": papers},
      indent=2))


if __name__ == "__main__":
  cli_args = parse_args()
  if not cli_args.query and not cli_args.id_list:
    print(json.dumps(
        {"status": "error",
         "message": "Must provide either --query or --id_list"}, indent=2))
    sys.exit(1)
  search_arxiv(cli_args)
