"""Read a reference library into library items for import_library.py.

Every reader returns items shaped {"title", "DOI", "arxiv", "PMID", "PMCID",
"author", "issued", "zotero", "pdf", "origin"}, with CSL JSON author and
issued values.
"""

import json
import pathlib
import re
import urllib.parse

import bibtexparser
import pymupdf
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import splitname
from bibtexparser.latexenc import latex_to_unicode

import http_client
import verify_citations
import zotero_local

_ARXIV_RE = re.compile(
    r"arxiv(?:\.org/abs/|:)\s*(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)
_BIB_FILE_DESC_RE = re.compile(r"^[^:/\\]*:(?=/|[A-Za-z]:|\w)")
_AND_RE = re.compile(r"\s+and\s+")
_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"'<>]+")


def _item(**fields) -> dict:
  item = {"title": None, "DOI": None, "arxiv": None, "PMID": None,
          "PMCID": None, "author": [], "issued": None, "zotero": None,
          "pdf": None, "origin": None}
  item.update(fields)
  return item


def from_csl(item: dict, zotero: str | None = None) -> dict:
  text = " ".join(str(item.get(name) or "")
                  for name in ("number", "URL", "note", "archive_location"))
  arxiv = _ARXIV_RE.search(text)
  return _item(title=item.get("title"), DOI=item.get("DOI"),
               arxiv=arxiv.group(1) if arxiv else None,
               PMID=item.get("PMID"), PMCID=item.get("PMCID"),
               author=item.get("author") or [], issued=item.get("issued"),
               zotero=zotero)


def read_csl(path: pathlib.Path) -> list[dict]:
  data = json.loads(path.read_text(encoding="utf-8"))
  if not isinstance(data, list):
    raise ValueError(f"{path} is not a CSL JSON array")
  return [from_csl(item) for item in data if isinstance(item, dict)]


def _unbrace(text: str | None) -> str | None:
  if text is None:
    return None
  return latex_to_unicode(text).replace("{", "").replace("}", "")


def _bib_author(name: str) -> dict:
  name = name.strip()
  if name.startswith("{") and name.endswith("}"):
    return {"literal": _unbrace(name)}
  parts = splitname(_unbrace(name), strict_mode=False)
  family = " ".join(parts.get("von", []) + parts.get("last", []))
  given = " ".join(parts.get("first", []))
  return {"family": family, "given": given} if given else {"family": family}


def _bib_pdf(field: str | None, base: pathlib.Path) -> str | None:
  for part in (field or "").split(";"):
    candidate = _BIB_FILE_DESC_RE.sub(
        "", part.strip().removesuffix(":application/pdf"), count=1)
    if candidate.lower().endswith(".pdf") and "\\" not in candidate:
      path = pathlib.Path(candidate)
      return str(path if path.is_absolute() else (base / path).resolve())
  return None


def _from_bibtex(entry: dict, base: pathlib.Path) -> dict:
  is_arxiv = (entry.get("archiveprefix") or "").lower() == "arxiv"
  year = re.match(r"\d{4}", entry.get("year") or "")
  pdf = _bib_pdf(entry.get("file"), base)
  return _item(
      title=_unbrace(entry.get("title")), DOI=entry.get("doi"),
      arxiv=entry.get("eprint") if is_arxiv else None,
      PMID=entry.get("pmid"), PMCID=entry.get("pmcid"),
      author=[_bib_author(n) for n in _AND_RE.split(entry.get("author") or "")
              if n.strip()],
      issued={"date-parts": [[int(year.group(0))]]} if year else None,
      pdf=pdf, origin={"kind": "file", "path": pdf} if pdf else None)


def read_bibtex(path: pathlib.Path) -> list[dict]:
  raw = path.read_text(encoding="utf-8")
  parser = BibTexParser(common_strings=True, ignore_nonstandard_types=False)
  try:
    entries = bibtexparser.loads(raw, parser=parser).entries
  except Exception as err:
    raise ValueError(f"cannot parse {path}: {err}") from err
  if not entries and "@" in raw:
    raise ValueError(f"no BibTeX entries could be parsed from {path}")
  return [_from_bibtex(entry, path.parent) for entry in entries]


def read_zotero(collection: str) -> tuple[list[dict], dict[str, int]]:
  root = zotero_local.collection_key(collection)
  names = zotero_local.collection_names()
  items, seen, counts = [], set(), {}
  for key in zotero_local.subcollection_keys(root):
    found = zotero_local.collection_items(key)
    counts[names.get(key, key)] = counts.get(names.get(key, key), 0) + len(found)
    for item_key, csl in found:
      if item_key in seen:
        continue
      seen.add(item_key)
      item = from_csl(csl, zotero=item_key)
      attachment = zotero_local.pdf_attachment(item_key)
      if attachment:
        path = zotero_local.attachment_path(attachment)
        item["pdf"] = str(path) if path else None
        item["origin"] = {"kind": "zotero", "item": item_key,
                          "attachment": attachment}
      items.append(item)
  return items, counts


def pdf_files(directory: pathlib.Path) -> list[pathlib.Path]:
  return sorted(p for p in directory.rglob("*")
                if p.is_file() and p.suffix.lower() == ".pdf")


def first_page_text(pdf: pathlib.Path) -> str:
  try:
    with pymupdf.open(pdf) as doc:
      return doc[0].get_text() if doc.page_count else ""
  except Exception:
    return ""


def first_page_doi(pdf: pathlib.Path) -> str | None:
  match = _DOI_RE.search(first_page_text(pdf))
  return match.group(0).rstrip(".,;:)]}") if match else None


def crossref_csl(doi: str) -> dict | None:
  path = (f"works/{urllib.parse.quote(doi, safe='/')}"
          "/transform/application/vnd.citationstyles.csl+json")
  try:
    data = verify_citations._CROSSREF.fetch_json(path)
  except http_client.HttpError:
    return None
  return data if isinstance(data, dict) else None


def read_pdf_folder(directory: pathlib.Path) -> tuple[list[dict], list[str]]:
  items, unmatched = [], []
  for pdf in pdf_files(directory):
    doi = first_page_doi(pdf)
    csl = crossref_csl(doi) if doi else None
    if csl is None:
      unmatched.append(str(pdf))
      continue
    item = from_csl(csl)
    item.update(pdf=str(pdf), origin={"kind": "file", "path": str(pdf)})
    items.append(item)
  return items, unmatched
