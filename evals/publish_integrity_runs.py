"""Publish selected literature-integrity runs for the dashboard."""

import argparse
import sys
from pathlib import Path

EVALS_DIR = Path(__file__).parent
sys.path.insert(0, str(EVALS_DIR))

from lib.run_reports import publish_runs  # noqa: E402


def main(argv=None) -> int:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("run_ids", nargs="+", metavar="RUN_ID")
  parser.add_argument("--source", type=Path, default=EVALS_DIR / "results")
  parser.add_argument("--published", type=Path, default=EVALS_DIR / "published")
  args = parser.parse_args(argv)
  try:
    publish_runs(args.source, args.published, args.run_ids)
  except (ValueError, FileExistsError) as exc:
    print(f"publish failed: {exc}", file=sys.stderr)
    return 1
  for run_id in args.run_ids:
    print(f"published {run_id}")
  return 0


if __name__ == "__main__":
  sys.exit(main())
