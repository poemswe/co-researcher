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

"""Verify a bibliography against OpenAlex, Crossref, and Europe PMC.

Reads citations from a JSON array, BibTeX (.bib), or a plain-text/markdown
file (one citation per line, DOIs extracted automatically) and resolves each
through OpenAlex, falling back to Europe PMC for DOIs.

Retraction is then checked down a ladder, because no single source is
complete. OpenAlex answers first. A DOI goes to Crossref, which carries the
Retraction Watch dataset — OpenAlex's own `is_retracted` missed 3 of 40
sampled retracted papers that Crossref caught. A paper with no DOI cannot be
in Crossref at all, so its PubMed record answers instead; that route also
backs up Crossref when Crossref cannot reply (an outage, or a DOI containing
a comma, which Crossref's filter language cannot express).

Every result records `retraction_checked` and `retraction_source`. A check
that could not run is reported as unchecked, never as clean.

Prints one JSON report to stdout:
  {"total", "verified", "mismatched", "not_found", "retracted", "results": [...]}
Exit code 0 when every citation verifies; 1 when any is mismatched,
not found, or retracted — usable as a pre-output gate against fabricated
and withdrawn references.
"""

# /// script
# requires-python = ">=3.10"
# ///

import argparse
import difflib
import json
import os
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
_CROSSREF_UA_ENV = "CO_RESEARCHER_USER_AGENT"
_DEFAULT_CROSSREF_UA = "co-researcher (https://github.com/poemswe/co-researcher)"


def crossref_user_agent() -> str:
  """Crossref's polite pool needs a contact; set the env var to a mailto UA."""
  return os.environ.get(_CROSSREF_UA_ENV) or _DEFAULT_CROSSREF_UA


_CROSSREF = http_client.HttpClient(
    "https://api.crossref.org/", qps=2.0, user_agent=crossref_user_agent())

_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"'<>]+")
_TITLE_MATCH_THRESHOLD = 0.85


def _extract_doi(text: str) -> str | None:
  match = _DOI_RE.search(text)
  if not match:
    return None
  return match.group(0).rstrip(".,;:)]}")


_BIB_ENTRY_START_RE = re.compile(
    r"^\s*@(?!(?:comment|string|preamble)\b)\w+\s*\{", re.IGNORECASE | re.MULTILINE)
_BIB_KEY_RE = re.compile(r"\{\s*([^,\s]+)\s*,")
_BIB_FIELD_RE = re.compile(
    r"(\w+)\s*=\s*(?:\{((?:[^{}]|\{[^{}]*\})*)\}|\"([^\"]*)\")")


def _parse_bibtex(raw: str) -> list[dict]:
  entries = []
  starts = list(_BIB_ENTRY_START_RE.finditer(raw))
  for i, match in enumerate(starts):
    end = starts[i + 1].start() if i + 1 < len(starts) else len(raw)
    chunk = raw[match.start():end]
    key_match = _BIB_KEY_RE.search(chunk)
    if not key_match:
      continue
    fields = {name.lower(): (braced or quoted).replace("{", "").replace("}", "")
              for name, braced, quoted in _BIB_FIELD_RE.findall(chunk)}
    entries.append({"doi": fields.get("doi"), "title": fields.get("title"),
                    "raw": key_match.group(1)})
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


def _pmid_from_openalex(work: dict) -> str | None:
  pmid_url = (work.get("ids") or {}).get("pmid") or ""
  return pmid_url.rstrip("/").rpartition("/")[2] or None


def resolve_doi(doi: str) -> dict | None:
  try:
    work = _OPENALEX.fetch_json(
        f"https://api.openalex.org/works/https://doi.org/{doi}")
    return {"title": work.get("title"), "doi": _doi_from_openalex(work) or doi,
            "source": "openalex", "retracted": bool(work.get("is_retracted")),
            "pmid": _pmid_from_openalex(work)}
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
          "source": "epmc", "retracted": False, "pmid": hits[0].get("pmid")}


def retracted_via_crossref(doi: str) -> bool | None:
  """Does a Crossref retraction notice point at this DOI?

  Crossref carries the Retraction Watch dataset. A retracted paper's own
  record does not always record the retraction, so ask the reverse question:
  which works update this DOI, and is any of them a retraction?

  Returns None when the answer is unknown — never False, which would read as
  "confirmed clean" and let a retracted paper through the gate.
  """
  if "," in doi:
    print(f"Cannot Crossref-check {doi}: a comma in the DOI would split the "
          "filter expression", file=sys.stderr)
    return None
  query = urllib.parse.urlencode(
      {"filter": f"updates:{doi},update-type:retraction", "rows": 0})
  try:
    data = _CROSSREF.fetch_json(f"https://api.crossref.org/works?{query}")
  except http_client.HttpError as err:
    print(f"Crossref retraction check failed for {doi}: {err}",
          file=sys.stderr)
    return None
  return data.get("message", {}).get("total-results", 0) > 0


def retracted_via_epmc(pmid: str) -> bool | None:
  """Does Europe PMC mark this PubMed record as retracted?

  Covers papers with no DOI, which cannot appear in Crossref at all.
  Europe PMC flags them two ways: a "Retracted Publication" publication
  type, or a "Retraction in" comment-correction entry.

  Returns None when the answer is unknown, never False.
  """
  query = urllib.parse.urlencode(
      {"query": f"EXT_ID:{pmid}", "format": "json", "resultType": "core"})
  try:
    data = _EPMC.fetch_json(f"search?{query}")
  except http_client.HttpError as err:
    print(f"Europe PMC retraction check failed for PMID {pmid}: {err}",
          file=sys.stderr)
    return None
  hits = data.get("resultList", {}).get("result", [])
  if not hits:
    return None
  article = hits[0]
  pub_types = (article.get("pubTypeList") or {}).get("pubType") or []
  if any("retracted" in t.lower() for t in pub_types):
    return True
  corrections = (article.get("commentCorrectionList") or {}).get(
      "commentCorrection") or []
  return any((c.get("type") or "").lower() == "retraction in"
             for c in corrections)


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
          "source": "openalex", "retracted": bool(hits[0].get("is_retracted")),
          "pmid": _pmid_from_openalex(hits[0])}


def _retraction_state(hit: dict) -> tuple[bool, bool, str | None]:
  """(retracted, checked, source) — checked is False only when unknowable.

  No single source is complete, so a clean answer from one does not end the
  search. OpenAlex answers first. A DOI goes to Crossref (Retraction Watch).
  Europe PMC's PubMed record is consulted whenever a PMID exists, since it
  reaches papers with no DOI — which cannot be in Crossref at all — and
  answers when Crossref cannot. A retraction found by any source wins.

  Measured, with the caveat that each sample is drawn from one source's own
  positives and so scores that source at 100% by construction: sampling
  Crossref's retracted set, OpenAlex missed 3 of 40; sampling PubMed's,
  Crossref missed 19 of 50 while OpenAlex missed none. Both other sources
  have measured holes, so the PubMed leg is kept as an independent third
  opinion — though no sampled paper was caught by it alone.
  """
  if hit["retracted"]:
    return True, True, "openalex"

  consulted = []
  if hit["doi"]:
    verdict = retracted_via_crossref(hit["doi"])
    if verdict is not None:
      if verdict:
        return True, True, "crossref"
      consulted.append("crossref")
  if hit.get("pmid"):
    verdict = retracted_via_epmc(hit["pmid"])
    if verdict is not None:
      if verdict:
        return True, True, "europepmc"
      consulted.append("europepmc")

  if not consulted:
    return False, False, None
  return False, True, "+".join(consulted)


def verify_one(entry: dict) -> dict:
  result = {"input": entry["raw"], "status": "not_found",
            "doi": entry.get("doi"), "matched_title": None, "source": None,
            "retraction_checked": False, "retraction_source": None}
  if entry.get("doi"):
    hit = resolve_doi(entry["doi"])
    if hit:
      retracted, checked, via = _retraction_state(hit)
      result.update(status="verified", doi=hit["doi"],
                    matched_title=hit["title"], source=hit["source"],
                    retraction_checked=checked, retraction_source=via)
      if retracted:
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
      retracted, checked, via = _retraction_state(hit)
      result.update(status="verified", doi=hit["doi"],
                    matched_title=hit["title"], source=hit["source"],
                    retraction_checked=checked, retraction_source=via)
      if retracted:
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
  line = (f"Citations: {counts['verified']} verified, "
          f"{counts['mismatched']} mismatched, "
          f"{counts['not_found']} not found, "
          f"{counts['retracted']} retracted (of {len(results)})")
  unchecked = sum(1 for r in results
                  if r["status"] == "verified" and not r["retraction_checked"])
  if unchecked:
    line += f"; {unchecked} not retraction-checked"
  print(line, file=sys.stderr)
  return 0 if len(results) == counts["verified"] else 1


if __name__ == "__main__":
  sys.exit(main())
