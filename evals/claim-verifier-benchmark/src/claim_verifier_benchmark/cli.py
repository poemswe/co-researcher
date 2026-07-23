from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import sys

from .canonical import build_manifest, manifest_digest
from .commitment import mapping_commitment
from .coverage_units import enumerate_coverage_units
from .split import Paper, derive_split_key, paper_order_key


def _read_json(path: pathlib.Path) -> dict:
  value = json.loads(path.read_text(encoding="utf-8"))
  if not isinstance(value, dict):
    raise ValueError(f"{path} must contain a JSON object")
  return value


def _parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(prog="claim-benchmark-core")
  subparsers = parser.add_subparsers(dest="command", required=True)

  split_parser = subparsers.add_parser("check-split-vector")
  split_parser.add_argument("vector_json", type=pathlib.Path)

  coverage_parser = subparsers.add_parser("enumerate-coverage")
  coverage_parser.add_argument("synthesis_md", type=pathlib.Path)

  manifest_parser = subparsers.add_parser("manifest")
  manifest_parser.add_argument("root", type=pathlib.Path)
  manifest_parser.add_argument("relative_paths", nargs="+")

  mapping_parser = subparsers.add_parser("commit-mapping")
  mapping_parser.add_argument("mapping_json", type=pathlib.Path)
  mapping_parser.add_argument("salt_hex")
  return parser


def _check_split_vector(path: pathlib.Path) -> dict:
  vector = _read_json(path)
  required = {
      "output_value",
      "construction_archive_sha256",
      "expected_split_key",
      "domain",
      "paper_ids",
      "expected_order",
  }
  if set(vector) != required:
    raise ValueError("split vector has missing or unexpected fields")
  paper_ids = vector["paper_ids"]
  expected_order = vector["expected_order"]
  if (not isinstance(paper_ids, list)
      or not isinstance(expected_order, list)
      or not all(isinstance(value, str) for value in paper_ids)
      or not all(isinstance(value, str) for value in expected_order)
      or len(paper_ids) != 5
      or len(set(paper_ids)) != 5
      or sorted(paper_ids) != sorted(expected_order)):
    raise ValueError("split vector paper IDs and expected order must match")
  split_key = derive_split_key(
      vector["output_value"], vector["construction_archive_sha256"])
  if split_key.hex() != vector["expected_split_key"]:
    raise ValueError("split key does not match the known-answer vector")
  papers = [Paper(stable_id=value, domain=vector["domain"])
            for value in paper_ids]
  observed = [
      paper.stable_id
      for paper in sorted(
          papers,
          key=lambda paper: (
              paper_order_key(split_key, paper),
              paper.stable_id.encode("utf-8"),
          ),
      )
  ]
  if observed != expected_order:
    raise ValueError("paper order does not match the known-answer vector")
  return {"valid": True}


def _enumerate_coverage(path: pathlib.Path) -> dict:
  synthesis = path.read_text(encoding="utf-8")
  units = enumerate_coverage_units(synthesis)
  return {
      "unit_count": len(units),
      "units": [dataclasses.asdict(unit) for unit in units],
  }


def _manifest(root: pathlib.Path, relative_paths: list[str]) -> dict:
  manifest = build_manifest(root, relative_paths)
  return {
      "manifest": manifest,
      "manifest_sha256": manifest_digest(manifest),
  }


def _commit_mapping(path: pathlib.Path, salt_hex: str) -> dict:
  if len(salt_hex) != 64:
    raise ValueError("mapping salt must contain exactly 64 hex characters")
  try:
    salt = bytes.fromhex(salt_hex)
  except ValueError as exc:
    raise ValueError("mapping salt is not hexadecimal") from exc
  mapping = _read_json(path)
  return {"mapping_commitment": mapping_commitment(mapping, salt)}


def main(argv: list[str] | None = None) -> int:
  try:
    args = _parser().parse_args(argv)
  except SystemExit as exc:
    return exc.code if isinstance(exc.code, int) else 2
  try:
    if args.command == "check-split-vector":
      output = _check_split_vector(args.vector_json)
    elif args.command == "enumerate-coverage":
      output = _enumerate_coverage(args.synthesis_md)
    elif args.command == "manifest":
      output = _manifest(args.root, args.relative_paths)
    elif args.command == "commit-mapping":
      output = _commit_mapping(args.mapping_json, args.salt_hex)
    else:
      raise ValueError(f"unknown command: {args.command}")
  except (OSError, UnicodeError, json.JSONDecodeError,
          TypeError, ValueError) as exc:
    print(f"error: {exc}", file=sys.stderr)
    return 2
  print(json.dumps(output, ensure_ascii=False, sort_keys=True))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
