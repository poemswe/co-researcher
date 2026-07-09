# MIT License
#
# Copyright (c) 2026 Poe Poe / co-researcher contributors
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT
# WARRANTY OF ANY KIND. See the MIT License for details.
#
# Original to this repository.

"""Verify a bibliography against OpenAlex and Europe PMC.

Reads citations from a JSON array, BibTeX (.bib), or a plain-text/markdown
file (one citation per line, DOIs extracted automatically) and resolves each
through OpenAlex,
falling back to Europe PMC for DOIs. Prints one JSON report to stdout:
  {"total", "verified", "mismatched", "not_found", "retracted", "results": [...]}
Exit code 0 when every citation verifies; 1 when any is mismatched,
not found, or retracted — usable as a pre-output gate against fabricated
references.
"""

# /// script
# requires-python = ">=3.10"
# ///

import argparse
import difflib
import json
import pathlib
import re
import sys
import urllib.parse

import http_client

_OPENALEX = http_client.HttpClient("https://api.openalex.org/", qps=1.0)
_EPMC = http_client.HttpClient(
    "https://www.ebi.ac.uk/europepmc/webservices/rest/",
    qps=1.0,
    referer_skill="literature-search-verify",
)

_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"'<>]+")
_TITLE_MATCH_THRESHOLD = 0.85


def _extract_doi(text: str) -> str | None:
  match = _DOI_RE.search(text)
  if not match:
    return None
  return match.group(0).rstrip(".,;:)]}")


_BIB_ENTRY_RE = re.compile(
    r"@(?!comment|string|preamble)\w+\s*\{\s*([^,\s]+)\s*,(.*?)\n\}",
    re.DOTALL | re.IGNORECASE)
_BIB_FIELD_RE = re.compile(
    r"(\w+)\s*=\s*(?:\{((?:[^{}]|\{[^{}]*\})*)\}|\"([^\"]*)\")")


def _parse_bibtex(raw: str) -> list[dict]:
  entries = []
  for key, body in _BIB_ENTRY_RE.findall(raw):
    fields = {name.lower(): (braced or quoted).replace("{", "").replace("}", "")
              for name, braced, quoted in _BIB_FIELD_RE.findall(body)}
    entries.append({"doi": fields.get("doi"), "title": fields.get("title"),
                    "raw": key})
  return entries


def parse_input(path: str) -> list[dict]:
  raw = pathlib.Path(path).read_text(encoding="utf-8")
  entries = []
  if path.endswith(".json"):
    for item in json.loads(raw):
      if isinstance(item, str):
        doi = _extract_doi(item)
        entries.append({"doi": doi, "title": None if doi else item,
                        "raw": item})
      else:
        entries.append({"doi": item.get("doi"), "title": item.get("title"),
                        "raw": json.dumps(item)})
    return entries
  if path.endswith(".bib"):
    return _parse_bibtex(raw)
  for line in raw.splitlines():
    line = line.strip().lstrip("-*").strip()
    if not line:
      continue
    entries.append({"doi": _extract_doi(line), "title": line, "raw": line})
  return entries


def _normalize_title(title: str) -> str:
  return re.sub(r"[^a-z0-9 ]", "", title.lower()).strip()


def titles_match(a: str, b: str) -> bool:
  na, nb = _normalize_title(a), _normalize_title(b)
  if not na or not nb:
    return False
  if na in nb or nb in na:
    return True
  return difflib.SequenceMatcher(None, na, nb).ratio() >= _TITLE_MATCH_THRESHOLD


def _doi_from_openalex(work: dict) -> str | None:
  doi_url = work.get("doi") or ""
  return doi_url.removeprefix("https://doi.org/") or None


def resolve_doi(doi: str) -> dict | None:
  try:
    work = _OPENALEX.fetch_json(
        f"https://api.openalex.org/works/https://doi.org/{doi}")
    return {"title": work.get("title"), "doi": _doi_from_openalex(work) or doi,
            "source": "openalex", "retracted": bool(work.get("is_retracted"))}
  except http_client.HttpError as err:
    if err.status_code != 404:
      print(f"OpenAlex error for DOI {doi}: {err}", file=sys.stderr)
  query = urllib.parse.urlencode(
      {"query": f'DOI:"{doi}"', "format": "json", "pageSize": 1})
  try:
    data = _EPMC.fetch_json(f"search?{query}")
  except http_client.HttpError as err:
    print(f"Europe PMC error for DOI {doi}: {err}", file=sys.stderr)
    return None
  hits = data.get("resultList", {}).get("result", [])
  if not hits:
    return None
  return {"title": hits[0].get("title"), "doi": hits[0].get("doi") or doi,
          "source": "epmc", "retracted": False}


def resolve_title(title: str) -> dict | None:
  query = urllib.parse.urlencode(
      {"filter": f"title.search:{title}", "per-page": 1})
  try:
    data = _OPENALEX.fetch_json(f"https://api.openalex.org/works?{query}")
  except http_client.HttpError as err:
    print(f"OpenAlex error for title {title!r}: {err}", file=sys.stderr)
    return None
  hits = data.get("results", [])
  if not hits or not titles_match(title, hits[0].get("title") or ""):
    return None
  return {"title": hits[0].get("title"), "doi": _doi_from_openalex(hits[0]),
          "source": "openalex", "retracted": bool(hits[0].get("is_retracted"))}


def verify_one(entry: dict) -> dict:
  result = {"input": entry["raw"], "status": "not_found",
            "doi": entry.get("doi"), "matched_title": None, "source": None}
  if entry.get("doi"):
    hit = resolve_doi(entry["doi"])
    if hit:
      result.update(status="verified", doi=hit["doi"],
                    matched_title=hit["title"], source=hit["source"])
      if hit["retracted"]:
        result["status"] = "retracted"
      else:
        claimed = entry.get("title")
        if (claimed and hit["title"] and _extract_doi(claimed) is None
            and not titles_match(claimed, hit["title"])):
          result["status"] = "mismatched"
    return result
  if entry.get("title"):
    hit = resolve_title(entry["title"])
    if hit:
      result.update(status="verified", doi=hit["doi"],
                    matched_title=hit["title"], source=hit["source"])
      if hit["retracted"]:
        result["status"] = "retracted"
  return result


def main(argv=None) -> int:
  parser = argparse.ArgumentParser(
      description="Verify citations against OpenAlex/Europe PMC.")
  parser.add_argument("--input", required=True,
                      help="Bibliography file: .json array or text/markdown, "
                           "one citation per line")
  args = parser.parse_args(argv)

  entries = parse_input(args.input)
  results = [verify_one(e) for e in entries]
  counts = {s: sum(1 for r in results if r["status"] == s)
            for s in ("verified", "mismatched", "not_found", "retracted")}
  print(json.dumps({"total": len(results), **counts, "results": results},
                   indent=2))
  print(f"Citations: {counts['verified']} verified, "
        f"{counts['mismatched']} mismatched, "
        f"{counts['not_found']} not found, "
        f"{counts['retracted']} retracted (of {len(results)})",
        file=sys.stderr)
  return 0 if len(results) == counts["verified"] else 1


if __name__ == "__main__":
  sys.exit(main())
