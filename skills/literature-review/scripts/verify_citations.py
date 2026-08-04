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
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
import pathlib
import re
import sys
import urllib.parse
from typing import Protocol

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


class ResolverUnavailable(RuntimeError):
  """The resolver could not answer; this is not authoritative not-found."""


class CitationResolver(Protocol):
  identity: str

  def resolve(self, entry: dict) -> dict:
    """Return one legacy-shaped citation result or raise unavailable."""


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
  if path.endswith(".json"):
    return normalize_citation_entries(json.loads(raw))
  if path.endswith(".bib"):
    return _parse_bibtex(raw)
  entries = []
  for line in raw.splitlines():
    line = line.strip().lstrip("-*").strip()
    if not line:
      continue
    entries.append({"doi": _extract_doi(line), "title": line, "raw": line})
  return entries


def normalize_citation_entries(items: list) -> list[dict]:
  """Normalize an ordered JSON bibliography into resolver inputs."""
  if not isinstance(items, list):
    raise ValueError("bibliography must be an ordered array")
  entries = []
  for index, item in enumerate(items):
    if isinstance(item, str):
      doi = _extract_doi(item)
      entries.append({"doi": doi, "title": None if doi else item,
                      "raw": item})
      continue
    if not isinstance(item, dict):
      raise ValueError(f"bibliography entry {index} must be a string or object")
    doi, title = item.get("doi"), item.get("title")
    if doi is not None and not isinstance(doi, str):
      raise ValueError(f"bibliography entry {index} doi must be a string")
    if title is not None and not isinstance(title, str):
      raise ValueError(f"bibliography entry {index} title must be a string")
    entries.append({"doi": doi, "title": title,
                    "raw": item.get("raw") if isinstance(item.get("raw"), str)
                    else json.dumps(item)})
  return entries


def _canonical_entry(entry: dict) -> dict:
  if not isinstance(entry, dict):
    raise ValueError("citation entry must be an object")
  doi, title, raw = entry.get("doi"), entry.get("title"), entry.get("raw")
  if doi is not None and not isinstance(doi, str):
    raise ValueError("citation doi must be a string or null")
  if title is not None and not isinstance(title, str):
    raise ValueError("citation title must be a string or null")
  if not isinstance(raw, str):
    raise ValueError("citation raw input must be a string")
  return {"doi": doi, "title": title}


def citation_input_identity(entry: dict) -> str:
  payload = json.dumps(
      _canonical_entry(entry), sort_keys=True, separators=(",", ":"),
      ensure_ascii=False).encode("utf-8")
  return hashlib.sha256(payload).hexdigest()


def bibliography_sha256(entries: list[dict]) -> str:
  if not isinstance(entries, list):
    raise ValueError("citation entries must be a list")
  payload = json.dumps(
      [_canonical_entry(entry) for entry in entries],
      sort_keys=True, separators=(",", ":"), ensure_ascii=False,
  ).encode("utf-8")
  return hashlib.sha256(payload).hexdigest()


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


def resolve_doi(doi: str, *, fail_on_unavailable: bool = False) -> dict | None:
  openalex_unavailable = False
  try:
    work = _OPENALEX.fetch_json(
        f"https://api.openalex.org/works/https://doi.org/{doi}")
    return {"title": work.get("title"), "doi": _doi_from_openalex(work) or doi,
            "source": "openalex", "retracted": bool(work.get("is_retracted")),
            "pmid": _pmid_from_openalex(work), "resolution_status": "complete"}
  except http_client.HttpError as err:
    if err.status_code != 404:
      print(f"OpenAlex error for DOI {doi}: {err}", file=sys.stderr)
      openalex_unavailable = True
  query = urllib.parse.urlencode(
      {"query": f'DOI:"{doi}"', "format": "json", "pageSize": 1})
  try:
    data = _EPMC.fetch_json(f"search?{query}")
  except http_client.HttpError as err:
    print(f"Europe PMC error for DOI {doi}: {err}", file=sys.stderr)
    if fail_on_unavailable:
      raise ResolverUnavailable(
          f"citation resolver unavailable for DOI {doi}") from err
    return None
  hits = data.get("resultList", {}).get("result", [])
  if not hits:
    if openalex_unavailable and fail_on_unavailable:
      raise ResolverUnavailable(
          f"citation resolver unavailable for DOI {doi}")
    return None
  return {"title": hits[0].get("title"), "doi": hits[0].get("doi") or doi,
          "source": "epmc", "retracted": False, "pmid": hits[0].get("pmid"),
          "resolution_status": "partial" if openalex_unavailable else "complete"}


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


def resolve_title(title: str, *, fail_on_unavailable: bool = False) -> dict | None:
  query = urllib.parse.urlencode(
      {"filter": f"title.search:{title}", "per-page": 1})
  try:
    data = _OPENALEX.fetch_json(f"https://api.openalex.org/works?{query}")
  except http_client.HttpError as err:
    print(f"OpenAlex error for title {title!r}: {err}", file=sys.stderr)
    if fail_on_unavailable:
      raise ResolverUnavailable(
          f"citation resolver unavailable for title {title!r}") from err
    return None
  hits = data.get("results", [])
  if not hits or not titles_match(title, hits[0].get("title") or ""):
    return None
  return {"title": hits[0].get("title"), "doi": _doi_from_openalex(hits[0]),
          "source": "openalex", "retracted": bool(hits[0].get("is_retracted")),
          "pmid": _pmid_from_openalex(hits[0]), "resolution_status": "complete"}


def _retraction_audit(hit: dict) -> tuple[bool, str, str | None]:
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
    return True, "complete", "openalex"

  consulted = []
  unavailable = 0
  applicable = 0
  if hit["doi"]:
    applicable += 1
    verdict = retracted_via_crossref(hit["doi"])
    if verdict is not None:
      if verdict:
        return True, "complete", "crossref"
      consulted.append("crossref")
    else:
      unavailable += 1
  if hit.get("pmid"):
    applicable += 1
    verdict = retracted_via_epmc(hit["pmid"])
    if verdict is not None:
      if verdict:
        return True, "complete", "europepmc"
      consulted.append("europepmc")
    else:
      unavailable += 1

  source = "+".join(consulted) or None
  if applicable == 0 or unavailable == applicable:
    return False, "unavailable", source
  if unavailable:
    return False, "partial", source
  return False, "complete", source


def _retraction_state(hit: dict) -> tuple[bool, bool, str | None]:
  """Legacy wrapper retaining the public checked boolean contract."""
  retracted, status, source = _retraction_audit(hit)
  return retracted, status == "complete", source


def verify_one(entry: dict, *, fail_on_unavailable: bool = False) -> dict:
  result = {"input": entry["raw"], "status": "not_found",
            "doi": entry.get("doi"), "matched_title": None, "source": None,
            "retraction_checked": False, "retraction_source": None,
            "retraction_status": "not_applicable",
            "resolution_status": "complete"}
  if entry.get("doi"):
    hit = resolve_doi(entry["doi"], fail_on_unavailable=fail_on_unavailable)
    if hit:
      retracted, audit_status, via = _retraction_audit(hit)
      result.update(status="verified", doi=hit["doi"],
                    matched_title=hit["title"], source=hit["source"],
                    retraction_checked=audit_status == "complete",
                    retraction_source=via,
                    retraction_status=audit_status,
                    resolution_status=hit.get("resolution_status", "complete"))
      if retracted:
        result["status"] = "retracted"
      else:
        claimed = entry.get("title")
        if (claimed and hit["title"] and _extract_doi(claimed) is None
            and not titles_match(claimed, hit["title"])):
          result["status"] = "mismatched"
    return result
  if entry.get("title"):
    hit = resolve_title(entry["title"],
                        fail_on_unavailable=fail_on_unavailable)
    if hit:
      retracted, audit_status, via = _retraction_audit(hit)
      result.update(status="verified", doi=hit["doi"],
                    matched_title=hit["title"], source=hit["source"],
                    retraction_checked=audit_status == "complete",
                    retraction_source=via,
                    retraction_status=audit_status,
                    resolution_status=hit.get("resolution_status", "complete"))
      if retracted:
        result["status"] = "retracted"
  return result


class NetworkCitationResolver:
  """Production resolver backed by the module's configured network clients."""

  identity = "openalex+crossref+europepmc"

  def resolve(self, entry: dict) -> dict:
    return verify_one(entry, fail_on_unavailable=True)


def _unavailable_result(entry: dict, message: str) -> dict:
  return {"input": entry.get("raw"), "status": "unavailable",
          "doi": entry.get("doi"), "matched_title": None, "source": None,
          "retraction_checked": False, "retraction_source": None,
          "retraction_status": "unavailable",
          "resolution_status": "unavailable",
          "error": message}


def _checked_at_iso(checked_at: datetime) -> str:
  if not isinstance(checked_at, datetime) or checked_at.tzinfo is None:
    raise ValueError("checked_at must be an aware datetime")
  offset = checked_at.utcoffset()
  if offset is None:
    raise ValueError("checked_at must be an aware datetime")
  if offset != timezone.utc.utcoffset(checked_at):
    raise ValueError("checked_at must be in UTC")
  return checked_at.astimezone(timezone.utc).isoformat().replace(
      "+00:00", "Z")


def _valid_resolver_result(result: object, entry: dict) -> bool:
  required = {
      "input", "status", "doi", "matched_title", "source",
      "retraction_checked", "retraction_source", "retraction_status",
      "resolution_status",
  }
  if not isinstance(result, dict) or not required <= set(result):
    return False
  status = result["status"]
  if status not in {
      "verified", "mismatched", "not_found", "retracted", "unavailable",
  }:
    return False
  if result["input"] != entry["raw"] or not isinstance(result["input"], str):
    return False
  if not all(result[field] is None or isinstance(result[field], str)
             for field in ("doi", "matched_title", "source",
                           "retraction_source")):
    return False
  if not isinstance(result["retraction_checked"], bool):
    return False
  audit = result["retraction_status"]
  if audit not in {"complete", "partial", "unavailable", "not_applicable"}:
    return False
  resolution = result["resolution_status"]
  if resolution not in {"complete", "partial", "unavailable"}:
    return False
  if status == "not_found":
    return (audit == "not_applicable" and not result["retraction_checked"]
            and resolution == "complete")
  if status == "unavailable":
    return (audit == "unavailable" and not result["retraction_checked"]
            and resolution == "unavailable")
  if status == "retracted":
    return audit == "complete" and result["retraction_checked"]
  return result["retraction_checked"] == (audit == "complete")


def verify_citation_entries(
    entries: list[dict], resolver: CitationResolver, checked_at: datetime,
) -> dict:
  """Deterministically verify explicit entries with an injected resolver."""
  if not isinstance(entries, list) or not all(
      isinstance(entry, dict) for entry in entries):
    raise ValueError("citation entries must be a list of objects")
  resolver_identity = getattr(resolver, "identity", None)
  if not isinstance(resolver_identity, str) or not resolver_identity:
    raise ValueError("resolver identity must be a non-empty string")
  checked_at_value = _checked_at_iso(checked_at)
  results = []
  commitment = bibliography_sha256(entries)
  for index, entry in enumerate(entries):
    input_identity = citation_input_identity(entry)
    try:
      result = resolver.resolve(entry)
    except ResolverUnavailable as exc:
      result = _unavailable_result(entry, str(exc) or "resolver unavailable")
    if not _valid_resolver_result(result, entry):
      raise ValueError("resolver result is malformed or internally inconsistent")
    status = result["status"]
    normalized = dict(result)
    normalized["entry_index"] = index
    normalized["input_identity"] = input_identity
    results.append(normalized)

  counts = {status: sum(1 for result in results
                        if result["status"] == status)
            for status in ("verified", "mismatched", "not_found", "retracted")}
  unavailable = sum(1 for result in results
                    if result["status"] == "unavailable")
  incomplete_retraction = any(
      result["status"] in {"verified", "mismatched"}
      and result.get("retraction_status") in {"partial", "unavailable"}
      for result in results)
  incomplete_resolution = any(
      result["resolution_status"] in {"partial", "unavailable"}
      for result in results)
  if unavailable == len(results) and results:
    response_status = "unavailable"
  elif unavailable or incomplete_retraction or incomplete_resolution:
    response_status = "partial"
  else:
    response_status = "complete"
  return {"total": len(results), **counts, "unavailable": unavailable,
          "resolver": resolver_identity, "checked_at": checked_at_value,
          "response_status": response_status,
          "bibliography_sha256": commitment, "results": results}


def main(argv=None) -> int:
  parser = argparse.ArgumentParser(
      description="Verify citations against OpenAlex/Europe PMC.")
  parser.add_argument("--input", required=True,
                      help="Bibliography file: .json array or text/markdown, "
                           "one citation per line")
  args = parser.parse_args(argv)

  entries = parse_input(args.input)
  report = verify_citation_entries(
      entries, NetworkCitationResolver(), datetime.now(timezone.utc))
  results = report["results"]
  counts = {status: report[status] for status in
            ("verified", "mismatched", "not_found", "retracted")}
  print(json.dumps(report, indent=2))
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
