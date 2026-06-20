# MIT License
#
# Copyright (c) 2026 Poe Poe / co-researcher contributors
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT
# WARRANTY OF ANY KIND. See the MIT License for details.
#
# Original to this repository. Wraps the public OpenAlex API; design inspired by
# google-deepmind/science-skills, no code copied.

"""OpenAlex API CLI — filter and search entities.

  uv run openalex_cli.py filter works --search "transformer" --per-page 10
"""

# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv",
# ]
# ///

import argparse
import json
import logging
import os
import sys
from typing import Any
import urllib.parse

import dotenv

import http_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

BASE_URL = "https://api.openalex.org"
_API_CLIENT = http_client.HttpClient(
    BASE_URL, qps=10.0, referer_skill="literature-search-openalex")

DEFAULT_PER_PAGE = 25
MAX_PER_PAGE = 100
MAX_RETRIES = 5
TRUNCATE_LINE_LIMIT = 500

ENTITY_TYPES = [
    "works", "authors", "sources", "institutions", "topics", "domains",
    "fields", "subfields", "sdgs", "countries", "continents", "languages",
    "keywords", "publishers", "funders", "awards", "work-types",
    "source-types", "institution-types", "licenses",
]


def _with_api_key(url: str, api_key: str | None) -> str:
  if not api_key:
    return url
  joiner = "&" if "?" in url else "?"
  return f"{url}{joiner}{urllib.parse.urlencode({'api_key': api_key})}"


def fetch_with_retry(url, params, api_key=None, max_retries=MAX_RETRIES,
                     exit_on_error=True):
  """Fetch JSON from OpenAlex; the API key is appended out of band of `params`."""
  query = urllib.parse.urlencode(params, doseq=True)
  full_url = _with_api_key(f"{url}?{query}" if query else url, api_key)
  try:
    return _API_CLIENT.fetch(full_url, max_retries=max_retries).json()
  except http_client.HttpError as err:
    if err.status_code == 429 and not api_key:
      logging.warning(
          "Rate limit (429) without an API key. Pass --api-key or set "
          "OPENALEX_API_KEY to raise the limit.")
    else:
      logging.error("HTTP %s while fetching %s: %s", err.status_code, url, err)
    if exit_on_error:
      sys.exit(1)
    return None


def print_json(data: Any) -> None:
  """Print JSON, truncating to TRUNCATE_LINE_LIMIT lines only on a TTY."""
  output = json.dumps(data, indent=2)
  if not sys.stdout.isatty():
    print(output)
    return
  lines = output.splitlines()
  if len(lines) > TRUNCATE_LINE_LIMIT:
    print("\n".join(lines[:TRUNCATE_LINE_LIMIT]))
    logging.warning(
        "Output truncated (%d more lines). Redirect to a file for the full data.",
        len(lines) - TRUNCATE_LINE_LIMIT)
  else:
    print(output)


def handle_filter(args: argparse.Namespace) -> None:
  """Filter/search an OpenAlex entity collection."""
  if args.sample is not None and args.sort is not None:
    logging.warning("--sort is ignored when --sample is used.")

  params = {
      key: getattr(args, key)
      for key in ("search", "filter", "group_by", "sample", "seed", "select")
      if getattr(args, key) is not None
  }
  if args.sort is not None and args.sample is None:
    params["sort"] = args.sort
  if args.group_by is None and args.sample is None:
    params["per_page"] = max(1, min(args.per_page, MAX_PER_PAGE))
    params["page"] = args.page

  data = fetch_with_retry(f"{BASE_URL}/{args.entity_type}", params,
                          api_key=args.api_key)
  count = (data.get("meta") or {}).get("count")
  if count is not None:
    print(f"OpenAlex: {count} total hits ({len(data.get('results') or [])} "
          "on this page)", file=sys.stderr)
  print_json(data)


def main(argv=None) -> None:
  dotenv.load_dotenv(os.path.expanduser("~/.env"))
  parser = argparse.ArgumentParser(description="OpenAlex API CLI")
  parser.add_argument("--api-key", dest="api_key",
                      default=os.environ.get("OPENALEX_API_KEY"),
                      help="API key for higher rate limits (or OPENALEX_API_KEY).")
  sub = parser.add_subparsers(dest="command", required=True)

  p = sub.add_parser("filter", help="Filter and search entities")
  p.add_argument("entity_type", choices=ENTITY_TYPES)
  p.add_argument("--search", help="Full-text search query")
  p.add_argument("--filter", help="Filter string (e.g. is_oa:true)")
  p.add_argument("--sort", help="Sort string (e.g. cited_by_count:desc)")
  p.add_argument("--group-by", dest="group_by", help="Group results by a field")
  p.add_argument("--per-page", dest="per_page", type=int,
                 default=DEFAULT_PER_PAGE,
                 help=f"Results per page (max {MAX_PER_PAGE})")
  p.add_argument("--page", type=int, default=1, help="Page number")
  p.add_argument("--sample", type=int, help="Number of random samples")
  p.add_argument("--seed", type=int, help="Seed for random sampling")
  p.add_argument("--select", help="Limit returned fields (e.g. id,title)")
  p.set_defaults(func=handle_filter)

  args = parser.parse_args(argv)
  args.func(args)


if __name__ == "__main__":
  main()
