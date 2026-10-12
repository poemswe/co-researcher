import collections
import hashlib
import json
import math
import pathlib
import statistics
import sys

HERE = pathlib.Path(__file__).parent
RUN = HERE.parent / "runs" / "run_20261008_015639_166787"


def synthesis_hash(label):
  snapshot = json.loads((RUN / "snapshots" / f"{label}.json").read_text())
  text = next(f["content"] for f in snapshot["files"] if f["path"] == "synthesis.md")
  return hashlib.sha256(text.encode()).hexdigest()


def main():
  result = json.loads((RUN / "result.json").read_text())
  rows = [json.loads(line) for line in (HERE / "rejudge.jsonl").read_text().splitlines()]
  scores = collections.defaultdict(list)
  for case in result["cases"]:
    rounds = [r["label"] for r in rows
              if r["label"].startswith(f"{case['case_id']}-round-")]
    if not rounds:
      continue
    final_label = max(rounds)
    for stage, label in (("first_pass", f"{case['case_id']}-first-pass"), ("final", final_label)):
      key = synthesis_hash(label)
      scores[key].append(case[stage]["quality_score"])
      scores[key].extend(r["quality_score"] for r in rows if r["label"] == label)
  groups = list(scores.values())
  df = sum(len(g) - 1 for g in groups)
  pooled = math.sqrt(sum((len(g) - 1) * statistics.variance(g) for g in groups) / df)
  ranges = [max(g) - min(g) for g in groups]
  clean = [r["quality_score"] for r in rows if r["label"] == "synthetic-valid-first-pass"]
  print(json.dumps({
      "texts": len(groups),
      "judgments_per_text": sorted({len(g) for g in groups}),
      "pooled_sd": round(pooled, 1),
      "median_range": round(statistics.median(ranges), 1),
      "max_range": round(max(ranges), 1),
      "clean_control_rescores": clean,
  }, indent=2))


if __name__ == "__main__":
  sys.exit(main())
