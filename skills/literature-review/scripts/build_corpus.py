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

"""Merge raw backend search results into a normalized corpus.json.

Reads any combination of OpenAlex, arXiv, and Europe PMC result files and
emits one record per paper, deduplicated by normalized DOI, else normalized
title, else a source identifier, in the schema `prisma_counts.py` and the
review protocol expect. A record carrying none of those is dropped with a
stderr warning rather than merged into an unrelated one. Papers found by
several backends get a joined `found_via` (e.g. "openalex+epmc") and the
highest `cited_by` any backend reported. Re-running against an existing
corpus.json preserves every screening decision, `fulltext` status, and `role`
already recorded, so a follow-up search never discards prior work.

`--epmc` also accepts `get_citations`/`get_references` output; pass
`--found-via snowball:citations` to label those candidates' provenance.
"""

# /// script
# requires-python = ">=3.10"
# ///

import argparse
import json
import pathlib
import re
import sys

_EMPTY_SCREENING = {"status": None, "stage": None, "reason": None}
_ID_FALLBACK_ORDER = ("arxiv", "pmcid", "pmid", "openalex")
_SKIPPED = {"count": 0}


def normalize_key(doi, title, ids=None):
  """Stable dedup key: DOI, else normalized title, else a source identifier.

  Returns None when nothing identifies the record. Never returns "" — two
  untitled papers must not collapse into one.
  """
  if doi:
    return doi.lower()
  slug = re.sub(r"[^a-z0-9]", "", (title or "").lower())
  if slug:
    return slug
  for name in _ID_FALLBACK_ORDER:
    value = (ids or {}).get(name)
    if value:
      return f"{name}:{value}"
  return None


def _record(doi, title, year, cited_by, found_via, ids):
  ids = {k: v for k, v in ids.items() if v}
  key = normalize_key(doi, title, ids)
  if key is None:
    _SKIPPED["count"] += 1
    print("Skipping record with no DOI, title, or identifier", file=sys.stderr)
    return None
  return {
      "key": key,
      "ids": ids,
      "title": title,
      "year": year,
      "cited_by": cited_by,
      "found_via": found_via,
      "screening": dict(_EMPTY_SCREENING),
      "fulltext": None,
      "role": None,
  }


def _read(path):
  return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _int_or_none(value):
  try:
    return int(value)
  except (TypeError, ValueError):
    return None


def load_openalex(path) -> list[dict]:
  records = []
  for work in _read(path).get("results", []):
    doi = (work.get("doi") or "").removeprefix("https://doi.org/") or None
    record = _record(
        doi, work.get("title"), _int_or_none(work.get("publication_year")),
        work.get("cited_by_count") or 0, "openalex",
        {"openalex": work.get("id"), "doi": doi})
    if record:
      records.append(record)
  return records


def load_arxiv(path) -> list[dict]:
  records = []
  for paper in _read(path).get("papers", []):
    record = _record(
        None, (paper.get("title") or "").strip(),
        _int_or_none((paper.get("published") or "")[:4]), 0, "arxiv",
        {"arxiv": paper.get("id")})
    if record:
      records.append(record)
  return records


def load_epmc(path) -> list[dict]:
  data = _read(path)
  hits = (data.get("results") or data.get("citations")
          or data.get("references") or [])
  records = []
  for hit in hits:
    record = _record(
        hit.get("doi"), hit.get("title"), _int_or_none(hit.get("pubYear")),
        _int_or_none(hit.get("citedByCount")) or 0, "epmc",
        {"doi": hit.get("doi"), "pmid": hit.get("pmid"),
         "pmcid": hit.get("pmcid")})
    if record:
      records.append(record)
  return records


def _absorb(target, incoming):
  sources = target["found_via"].split("+")
  for source in incoming["found_via"].split("+"):
    if source not in sources:
      sources.append(source)
  target["found_via"] = "+".join(sources)
  target["ids"].update(incoming["ids"])
  target["cited_by"] = max(target["cited_by"], incoming["cited_by"])
  target["title"] = target["title"] or incoming["title"]
  target["year"] = target["year"] or incoming["year"]
  if incoming["screening"]["status"] and not target["screening"]["status"]:
    target["screening"] = incoming["screening"]
  target["fulltext"] = target["fulltext"] or incoming["fulltext"]
  target["role"] = target["role"] or incoming["role"]


def merge(records: list[dict]) -> list[dict]:
  merged: dict[str, dict] = {}
  for record in records:
    key = record["key"]
    if key in merged:
      _absorb(merged[key], record)
    else:
      merged[key] = dict(record)
  return list(merged.values())


def main(argv=None) -> int:
  parser = argparse.ArgumentParser(
      description="Merge backend search results into a corpus.json.")
  parser.add_argument("--openalex", action="append", default=[])
  parser.add_argument("--arxiv", action="append", default=[])
  parser.add_argument("--epmc", action="append", default=[])
  parser.add_argument("--found-via", dest="found_via",
                      help="Override the provenance label for every input in "
                           "this run, e.g. snowball:citations")
  parser.add_argument("--output", required=True)
  args = parser.parse_args(argv)

  _SKIPPED["count"] = 0
  output = pathlib.Path(args.output)
  records = _read(output) if output.exists() else []
  incoming = []
  for path in args.openalex:
    incoming.extend(load_openalex(path))
  for path in args.arxiv:
    incoming.extend(load_arxiv(path))
  for path in args.epmc:
    incoming.extend(load_epmc(path))
  if args.found_via:
    for record in incoming:
      record["found_via"] = args.found_via

  corpus = merge(records + incoming)
  output.parent.mkdir(parents=True, exist_ok=True)
  output.write_text(json.dumps(corpus, indent=1), encoding="utf-8")

  by_source: dict[str, int] = {}
  for record in corpus:
    by_source[record["found_via"]] = by_source.get(record["found_via"], 0) + 1
  summary = ", ".join(f"{v} {k}" for k, v in sorted(by_source.items()))
  line = f"Corpus: {len(corpus)} records after dedup ({summary})"
  skipped = _SKIPPED["count"]
  if skipped:
    noun = "record" if skipped == 1 else "records"
    line += f"; {skipped} {noun} skipped (unidentifiable)"
  print(line, file=sys.stderr)
  return 0


if __name__ == "__main__":
  sys.exit(main())
