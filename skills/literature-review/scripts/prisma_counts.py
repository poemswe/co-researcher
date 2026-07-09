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

"""Compute PRISMA 2020 flow counts from a review workspace corpus.json.

Prints one JSON object to stdout (identified_by_source, after_dedup,
screened, excluded-by-reason, included, not_retrieved, in_synthesis) and a
human summary to stderr. Exits 1 if any excluded record lacks a reason —
exclusion reasons are mandatory in the review protocol.
"""

# /// script
# requires-python = ">=3.10"
# ///

import argparse
import collections
import json
import pathlib
import sys


def load_records(path: str) -> list[dict]:
  data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
  if isinstance(data, dict):
    data = data.get("records") or data.get("papers") or []
  return data


def compute(records: list[dict]) -> dict:
  by_source = collections.Counter(
      r.get("found_via") or "unknown" for r in records)
  screening = [r.get("screening") or {} for r in records]
  excluded = collections.Counter(
      s.get("reason") or "unspecified"
      for s in screening if s.get("status") == "excluded")
  included = [r for r in records
              if (r.get("screening") or {}).get("status") == "included"]
  not_retrieved = sum(1 for r in included
                      if r.get("fulltext") != "fulltext")
  return {
      "identified_by_source": dict(by_source),
      "after_dedup": len(records),
      "screened": sum(1 for s in screening if s.get("status")),
      "excluded": dict(excluded),
      "included": len(included),
      "not_retrieved": not_retrieved,
      "in_synthesis": len(included) - not_retrieved,
  }


def main(argv=None) -> int:
  parser = argparse.ArgumentParser(
      description="PRISMA 2020 flow counts from corpus.json.")
  parser.add_argument("--corpus", required=True)
  args = parser.parse_args(argv)

  counts = compute(load_records(args.corpus))
  print(json.dumps(counts, indent=2))
  print(f"PRISMA: {counts['after_dedup']} records, "
        f"{counts['screened']} screened, {counts['included']} included, "
        f"{counts['in_synthesis']} in synthesis", file=sys.stderr)
  if counts["excluded"].get("unspecified"):
    print("ERROR: excluded records without a reason — exclusion reasons "
          "are mandatory", file=sys.stderr)
    return 1
  return 0


if __name__ == "__main__":
  sys.exit(main())
