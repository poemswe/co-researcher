import json
import pathlib
import sys
from concurrent.futures import ThreadPoolExecutor

R = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(R / "evals"))
from lib import literature_integrity as li  # noqa: E402

run_dir, model, out_path = pathlib.Path(sys.argv[1]), sys.argv[2], pathlib.Path(sys.argv[3])
plan = json.loads(sys.argv[4])

cases = {c.case_id: c for c in li.load_cases(R / "evals/test-cases/literature-review-integrity")}
judge = li.ProductionQualityJudge(model)


def synthesis(label):
  snapshot = json.loads((run_dir / "snapshots" / f"{label}.json").read_text())
  return next(f["content"] for f in snapshot["files"] if f["path"] == "synthesis.md")


jobs = [(label, repeat) for label, repeats in plan.items() for repeat in range(repeats)]


def run(job):
  label, repeat = job
  case_id = label.rsplit("-first-pass", 1)[0].rsplit("-round-", 1)[0]
  text = synthesis(label)
  result = judge.score(cases[case_id], text)
  return {"label": label, "repeat": repeat, "quality_score": result.quality_score,
          "error": result.error, "chars": len(text)}


with ThreadPoolExecutor(max_workers=3) as pool, out_path.open("a") as out:
  for row in pool.map(run, jobs):
    out.write(json.dumps(row) + "\n")
    out.flush()
    print(row, flush=True)
