"""Import a reference library into a literature-review workspace.

Reads one Zotero collection (local API), BibTeX or CSL JSON export, or folder
of PDFs; writes library.json for `build_corpus.py --library`; copies each
matched PDF to papers/{id}/paper.pdf with a paper.origin.json; and prints one
JSON summary line naming every item the review cannot fully stand behind.
"""

# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pymupdf",
#   "bibtexparser>=1.4,<2",
# ]
# ///

import argparse
import json
import pathlib
import shutil
import sys

import build_corpus
import check_claims
import library_sources
import verify_citations
import zotero_local

_REGISTRY_FIELDS = ("DOI", "arxiv", "PMID", "PMCID")


def _label(item: dict) -> str:
  return item.get("title") or item.get("DOI") or "(untitled)"


def paper_dir_name(item: dict) -> str:
  ids = build_corpus.library_ids(item)
  identifier = (ids["doi"] or ids["arxiv"] or ids["pmcid"]
                or build_corpus.normalize_key(None, item.get("title"), ids))
  return check_claims.sanitize_id(identifier or "")


def resolve_missing_dois(items: list[dict]) -> list[str]:
  resolved = []
  for item in items:
    if not item.get("title") or any(
        item.get(name) for name in ("DOI", "arxiv", "PMCID")):
      continue
    hit = verify_citations.resolve_title(item["title"])
    if hit and hit.get("doi"):
      item["DOI"] = hit["doi"]
      resolved.append(item["title"])
  return resolved


def _has_pdf(item: dict) -> bool:
  return bool(item.get("pdf")) and pathlib.Path(item["pdf"]).is_file()


def match_pdf_dir(items: list[dict], pdf_dir: pathlib.Path):
  found, unmatched = {}, []
  for pdf in library_sources.pdf_files(pdf_dir):
    doi = library_sources.first_page_doi(pdf)
    if doi:
      found.setdefault(check_claims.doi_key(doi), []).append(pdf)
    else:
      unmatched.append(str(pdf))
  claimed, conflicts = set(), []
  for item in items:
    key = build_corpus.library_ids(item)["doi"]
    if _has_pdf(item) or not key:
      continue
    pdfs = found.get(key, [])
    if pdfs:
      claimed.add(key)
    if len(pdfs) == 1:
      item["pdf"] = str(pdfs[0])
      item["origin"] = {"kind": "file", "path": str(pdfs[0])}
    elif len(pdfs) > 1:
      conflicts.extend(str(p) for p in pdfs)
  unmatched += [str(p) for key, pdfs in found.items() if key not in claimed
                for p in pdfs]
  return unmatched, conflicts


def place_pdf(item: dict, workspace: pathlib.Path) -> bool:
  directory = workspace / "papers" / paper_dir_name(item)
  target = directory / "paper.pdf"
  source = pathlib.Path(item["pdf"])
  if target.exists():
    return target.read_bytes() == source.read_bytes()
  if (directory / "fulltext.md").exists():
    return False
  directory.mkdir(parents=True, exist_ok=True)
  shutil.copyfile(source, target)
  (directory / "paper.origin.json").write_text(
      json.dumps(item["origin"], indent=2) + "\n", encoding="utf-8")
  return True


def _read(args) -> tuple[str, list[dict], dict, list[str]]:
  if args.zotero:
    items, counts = library_sources.read_zotero(args.zotero)
    return "zotero", items, counts, []
  if args.file:
    path = pathlib.Path(args.file)
    if path.suffix.lower() == ".bib":
      return "bibtex", library_sources.read_bibtex(path), {}, []
    if path.suffix.lower() == ".json":
      return "csl", library_sources.read_csl(path), {}, []
    raise ValueError(f"--file must be a .bib or .json export: {path}")
  items, unmatched = library_sources.read_pdf_folder(pathlib.Path(args.pdf_dir))
  return "pdf_folder", items, {}, unmatched


def parse_args(argv):
  parser = argparse.ArgumentParser(
      description="Import a reference library into a review workspace.")
  source = parser.add_mutually_exclusive_group()
  source.add_argument("--zotero", help="Zotero collection key or name")
  source.add_argument("--file", help="BibTeX (.bib) or CSL JSON (.json) export")
  parser.add_argument("--pdf-dir", help="Folder of PDFs to match or import")
  parser.add_argument("--workspace", required=True,
                      help="Absolute review workspace directory")
  args = parser.parse_args(argv)
  if not (args.zotero or args.file or args.pdf_dir):
    parser.error("pass --zotero, --file or --pdf-dir")
  return args


def main(argv=None) -> int:
  args = parse_args(argv)
  workspace = pathlib.Path(args.workspace)
  if not workspace.is_absolute():
    print(f"import_library: --workspace must be absolute: {workspace}",
          file=sys.stderr)
    return 2
  try:
    source, items, counts, unmatched = _read(args)
  except (ValueError, OSError, zotero_local.ZoteroUnavailable) as err:
    print(f"import_library: {err}", file=sys.stderr)
    return 1
  doi_resolved = resolve_missing_dois(items)
  conflicts = []
  if args.pdf_dir and source != "pdf_folder":
    more_unmatched, conflicts = match_pdf_dir(items, pathlib.Path(args.pdf_dir))
    unmatched += more_unmatched
  placed, no_text = 0, []
  for item in items:
    if not _has_pdf(item):
      continue
    if not place_pdf(item, workspace):
      conflicts.append(str(workspace / "papers" / paper_dir_name(item)))
      continue
    placed += 1
    if not library_sources.first_page_text(pathlib.Path(item["pdf"])).strip():
      no_text.append(_label(item))
  workspace.mkdir(parents=True, exist_ok=True)
  (workspace / "library.json").write_text(
      json.dumps({"source": source, "items": items}, indent=1),
      encoding="utf-8")
  print(json.dumps({
      "items": len(items),
      "by_collection": counts,
      "pdfs_matched": placed,
      "no_pdf": sum(1 for i in items if not i.get("origin")),
      "no_identifier": [_label(i) for i in items
                        if not any(i.get(f) for f in _REGISTRY_FIELDS)],
      "no_text_layer": no_text,
      "missing_on_disk": [_label(i) for i in items
                          if i.get("origin") and not _has_pdf(i)],
      "unmatched_files": unmatched,
      "conflicts": conflicts,
      "doi_resolved": doi_resolved,
  }))
  return 0


if __name__ == "__main__":
  sys.exit(main())
