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

"""Verify that each claim's supporting quote is genuinely in its cited source.

The agent supplies claims.json entries {claim, paper_id, citation,
supporting_quote, role?}; this gate proves the quote exists in
papers/{paper_id}/fulltext.md
(or abstract.md), flags quotes missing the claim's numbers, and — given
--synthesis — hard-fails every cited source without a text- and
citation-matching claim entry, so the gate cannot be starved of input. Quote
search uses character coverage to find candidates, then rejects meaningful
wording differences while allowing recognizable PDF extraction artifacts.
Citation identities are bound to trusted corpus author/year metadata or, for
numeric styles, to an ordered bibliography supplied with --references.

Exit 0 only when every claim is verified or verified as background; unresolved
review flags and source, quote, or coverage failures return nonzero.
"""

# /// script
# requires-python = ">=3.10"
# ///

import argparse
import collections
import difflib
import json
import pathlib
import re
import sys
import unicodedata

_QUOTE_MATCH_THRESHOLD = 0.90
_COVERAGE_MATCH_THRESHOLD = 0.80
_MIN_QUOTE_CHARS = 40
_MIN_QUOTE_WORDS = 8

_CHAR_MAP = str.maketrans({
    "“": '"', "”": '"', "‘": "'", "’": "'",
    "–": "-", "—": "-", "−": "-", "­": "",
})

_MEANINGFUL_RE = re.compile(r"[a-z0-9%<>=\u2264\u2265\u00b1]")
_GAP_POLARITY_RE = re.compile(
    r"\b(?:not|no|never|neither|without|increase[ds]?|decrease[ds]?|"
    r"reduce[ds]?|raise[ds]?|lower(?:ed|s)?|improve[ds]?|worsen(?:ed|s)?)\b"
    r"|[%<>=\u2264\u2265\u00b1]")
_AUTHOR_HEADER_RE = re.compile(
    r"(?:[a-z][a-z'\u2019.-]*\s+){0,6}et al\.?\s+"
    r"(?:19|20)\d{2}(?:\s+\d+)?$")


def normalize_text(text: str) -> str:
  text = unicodedata.normalize("NFKC", text).translate(_CHAR_MAP)
  text = re.sub(r"(\w)-\s+(\w)", r"\1\2", text)
  return re.sub(r"\s+", " ", text.lower()).strip()


def _coverage(matcher: difflib.SequenceMatcher, quote_len: int) -> float:
  matched = sum(b.size for b in matcher.get_matching_blocks())
  return matched / quote_len if quote_len else 0.0


def _best_window(quote: str, source: str) -> tuple[float, str, int]:
  qlen = len(quote)
  step = max(1, qlen // 2)
  # A repeated header can expand the real source span beyond 1.5x the quote.
  # A 2x window guarantees one sampled window contains any span up to 1.5x.
  wlen = qlen * 2
  matcher = difflib.SequenceMatcher(autojunk=False)
  matcher.set_seq2(quote)
  prefilter = 2 * _QUOTE_MATCH_THRESHOLD * qlen / (wlen + qlen)
  best_cov, best_win, best_start = 0.0, source[:wlen], 0
  for start in range(0, max(1, len(source) - qlen + 1), step):
    window = source[start:start + wlen]
    matcher.set_seq1(window)
    if matcher.real_quick_ratio() < prefilter:
      continue
    if matcher.quick_ratio() < prefilter:
      continue
    cov = _coverage(matcher, qlen)
    if cov > best_cov:
      best_cov, best_win, best_start = cov, window, start
  return best_cov, best_win, best_start


def _numbers_grounded(quote: str, source: str, locate) -> bool:
  """Every quote number must equal the complete source token it aligns to.

  `locate(qs, qe)` returns the absolute source position of the quote number at
  [qs, qe), or None if it does not align to one contiguous source region. The
  source token spanning that position must equal the quote's number. This
  blocks every number-fabrication class seen so far — swap, neighbour, digit
  subset/superset (`18` vs `108`/`118`/`181`), decimal shift (`2.5` vs `12.5`,
  `5` vs `.5`), and sign flip (`18` vs `-18`) — on both the exact and fuzzy
  paths. Years are excluded from grounding, by design.
  """
  for qs, qe, qtok in extract_number_spans(quote, exclude_years=False):
    pos = locate(qs, qe)
    if pos is None or _source_number_covering(source, pos) != qtok:
      return False
  return True


def _window_locator(quote: str, window: str, offset: int):
  """Map a quote span to its absolute source position via quote↔window blocks."""
  blocks = difflib.SequenceMatcher(
      None, quote, window, autojunk=False).get_matching_blocks()

  def locate(qs, qe):
    for b in blocks:
      if b.a <= qs and qe <= b.a + b.size:
        return offset + b.b + (qs - b.a)
    return None
  return locate


def _allowed_source_gap(text: str) -> bool:
  """Accept punctuation/spacing or a tightly structured PDF artifact."""
  gap = text.strip(" \t\n.,;:()[]{}-\u2013\u2014")
  if not _MEANINGFUL_RE.search(gap):
    return True
  if _GAP_POLARITY_RE.search(gap) or len(gap) > 180:
    return False
  if "|" in gap:
    return True
  if re.fullmatch(r"(?:page\s+)?\d+(?:\s+of\s+\d+)?", gap):
    return True
  if re.search(r"\b(?:header|page|journal|vol(?:ume)?|doi|copyright|preprint|"
               r"arxiv|pmc)\b",
               gap) and len(gap.split()) <= 20:
    return True
  return bool(_AUTHOR_HEADER_RE.fullmatch(gap))


def _aligned_source_span(quote: str, window: str, offset: int) -> tuple[int, int]:
  blocks = [b for b in difflib.SequenceMatcher(
      None, quote, window, autojunk=False).get_matching_blocks() if b.size]
  return offset + blocks[0].b, offset + blocks[-1].b + blocks[-1].size


def _authentic_alignment(quote: str, window: str) -> bool:
  """Reject wording changes while tolerating source-side PDF artifacts.

  Coverage alone is asymmetric: deleting `not` or `%` from a source can still
  give a quote 100% coverage. This opcode check rejects every meaningful
  quote-side edit and every meaningful source insertion inside the aligned
  passage unless the insertion has a recognizable page/header marker.
  Context before and after the aligned quote is ignored.
  """
  matcher = difflib.SequenceMatcher(None, quote, window, autojunk=False)
  blocks = [b for b in matcher.get_matching_blocks() if b.size]
  if not blocks:
    return False
  source_start = blocks[0].b
  source_end = blocks[-1].b + blocks[-1].size
  for tag, q1, q2, s1, s2 in matcher.get_opcodes():
    if tag == "equal":
      continue
    if tag == "insert" and (s2 <= source_start or s1 >= source_end):
      continue
    quote_gap = quote[q1:q2]
    source_gap = window[s1:s2]
    if _MEANINGFUL_RE.search(quote_gap):
      return False
    if source_start < s2 and s1 < source_end and not _allowed_source_gap(
        source_gap):
      return False
  return True


def find_quote(quote: str, source: str) -> dict:
  """Locate the quote in the source: exact, fuzzy window, or per-sentence.

  Per-sentence fallback accepts a multi-sentence quote only when its sentences
  match in source order within 3x the quote's length — generous enough for one
  mid-quote PDF artifact (a page header, caption), tight enough to reject
  sentences stitched from distant sections.
  """
  idx = source.find(quote)
  if idx != -1 and _numbers_grounded(quote, source, lambda qs, qe: idx + qs):
    return {"coverage": 1.0, "window": quote, "method": "exact",
            "start": idx, "end": idx + len(quote)}
  cov, window, start = _best_window(quote, source)
  if (cov >= _QUOTE_MATCH_THRESHOLD and _authentic_alignment(quote, window)
      and _numbers_grounded(
          quote, source, _window_locator(quote, window, start))):
    match_start, match_end = _aligned_source_span(quote, window, start)
    return {"coverage": cov, "window": window, "method": "fuzzy",
            "start": match_start, "end": match_end}
  sentences = [s for s in re.split(r"(?<=[.!?])\s+", quote) if s]
  if len(sentences) >= 2 and all(len(s) >= 20 for s in sentences):
    per = [find_quote(s, source) for s in sentences]
    if all(p["method"] is not None for p in per):
      starts = [p["start"] for p in per]
      ends = [p["end"] for p in per]
      span = max(ends) - min(starts)
      gaps = [source[ends[i]:starts[i + 1]] for i in range(len(per) - 1)]
      if (starts == sorted(starts) and span <= 3 * len(quote)
          and all(_allowed_source_gap(gap) for gap in gaps)):
        worst = min(per, key=lambda p: p["coverage"])
        return {"coverage": worst["coverage"],
                "window": source[min(starts):max(ends)],
                "method": "per_sentence", "start": min(starts),
                "end": max(ends)}
  return {"coverage": cov, "window": window, "method": None,
          "start": start, "end": None}


def _boundary_context_risks(source: str, start: int, end: int) -> list[str]:
  """Flag nearby polarity that an exact excerpt may have trimmed away."""
  before = source[max(0, start - 60):start]
  after = source[end:end + 60]
  risks = []
  if re.search(r"\b(?:not|no|never|neither|without)\s+(?:\w+\s+){0,3}$",
               before):
    risks.append("leading_negation_context")
  if re.match(r"^(?:\W*\w+\s+){0,2}(?:not|never|without)\b", after):
    risks.append("trailing_negation_context")
  return risks


_STOPWORDS = frozenset("""
a about after all also among an and any are as at be been between both but
by can could did do does during each few for from further had has have how
if in into is it its more most no nor not of on or other our over same
should so some such than that the their then there these they this those
through to under until up very was we were what when where which while who
will with would
study studies results result findings finding suggests suggested data
showed shown show analysis analyses effect effects outcome outcomes
significant significantly participants patients group groups trial trials
research paper authors evidence
""".split())

_NUMBER_RE = re.compile(r"[-+]?(?:\d+(?:,\d{3})*(?:\.\d+)?|\.\d+)")


def _norm_num(token: str) -> str:
  return token.replace(",", "")


def extract_number_spans(text: str,
                         exclude_years: bool = True) -> list[tuple[int, int, str]]:
  """(start, end, normalized token) per number.

  Tokens keep a leading sign and decimals (`-18`, `.5`, `12.5`) so grounding
  compares whole numbers, not digit fragments. `exclude_years` drops 4-digit
  years — right for the claim/anchor check (a citation year need not appear in
  the quote), wrong for quote-vs-source grounding (a year in the quoted
  passage must genuinely appear in the source, and a fabricated value that
  merely falls in the year range must not be waved through).
  """
  spans = []
  for m in _NUMBER_RE.finditer(text):
    plain = _norm_num(m.group())
    digits = plain.lstrip("+-")
    if (exclude_years and len(digits) == 4 and digits.isdigit()
        and 1900 <= int(digits) <= 2099):
      continue
    spans.append((m.start(), m.end(), plain))
  return spans


def _source_number_covering(source: str, pos: int) -> str | None:
  """The complete source number token spanning position `pos`, normalized.

  Uses the same tokenizer as the quote, so `18` cannot match a source `118`,
  `-18`, or the `.5` of `12.5` — the full aligned source token must equal the
  quote's number, not merely contain its digits.
  """
  lo = max(0, pos - 24)
  for m in _NUMBER_RE.finditer(source[lo:pos + 24]):
    if m.start() <= pos - lo < m.end():
      return _norm_num(m.group())
  return None


def extract_numbers(text: str) -> list[str]:
  numbers = []
  for _, _, plain in extract_number_spans(text):
    if plain not in numbers:
      numbers.append(plain)
  return numbers


def extract_words(text: str) -> list[str]:
  words = []
  for word in re.findall(r"[a-z]+", normalize_text(text)):
    if len(word) > 3 and word not in _STOPWORDS and word not in words:
      words.append(word)
  return words


def sanitize_id(identifier: str) -> str:
  safe = re.sub(r"[^A-Za-z0-9._-]", "_", identifier)
  return re.sub(r"^\.+", "_", safe) or "_"


def _read_json(path: pathlib.Path, label: str):
  try:
    return json.loads(path.read_text(encoding="utf-8"))
  except (OSError, json.JSONDecodeError) as err:
    sys.exit(f"Cannot read {label} file {path}: {err}")


def _record_ids(record: dict) -> set[str]:
  values = [record.get("key"), *(record.get("ids") or {}).values()]
  return {sanitize_id(str(value).removeprefix("https://doi.org/"))
          for value in values if value}


def _corpus_records(workspace) -> list[dict]:
  path = pathlib.Path(workspace) / "corpus.json"
  records = _read_json(path, "corpus")
  if not isinstance(records, list) or not all(
      isinstance(record, dict) for record in records):
    sys.exit("corpus.json must be a JSON array of objects")
  return records


def _record_for_paper_id(records: list[dict], paper_id: str) -> dict | None:
  matches = [record for record in records
             if sanitize_id(paper_id) in _record_ids(record)]
  if len(matches) > 1:
    sys.exit(f"paper_id {paper_id!r} matches multiple corpus records")
  return matches[0] if matches else None


_NAME_PARTICLES = frozenset(
    "al da de del della der di dos du la le van von".split())


def _name_aliases(name: str) -> set[str]:
  """Trusted full-name and surname aliases for an in-text first author."""
  normalized = _author_key(name)
  if not normalized:
    return set()
  if "," in name:
    surname = _author_key(name.split(",", 1)[0])
  else:
    words = normalized.split()
    end = len(words)
    if end > 1 and (len(words[-1]) <= 2 or
                    re.fullmatch(r"[a-z](?: [a-z])?", " ".join(words[-2:]))):
      end -= 1
    start = max(0, end - 1)
    while start > 0 and words[start - 1] in _NAME_PARTICLES:
      start -= 1
    surname = " ".join(words[start:end])
  return {normalized, surname}


def _author_year_binding_matches(key: str, record: dict) -> bool:
  _, author, year = key.split(":", 2)
  if str(record.get("year") or "").lower() != year.rstrip("abcdefghijklmnopqrstuvwxyz"):
    return False
  authors = record.get("authors") or []
  if not authors:
    return False
  aliases = _name_aliases(authors[0])
  return any(author == alias or author.startswith(alias + " ")
             for alias in aliases)


def _normalize_bib_title(title: str) -> str:
  return re.sub(r"[^a-z0-9]+", "", title.lower())


def _reference_record(item, records: list[dict]) -> dict | None:
  doi = title = None
  if isinstance(item, dict):
    doi, title = item.get("doi"), item.get("title")
  elif isinstance(item, str):
    match = re.search(r"10\.\d{4,9}/[^\s\"'<>]+", item)
    doi = match.group(0).rstrip(".,;:)]}") if match else None
    title = None if doi else item
  if doi:
    needle = doi.removeprefix("https://doi.org/").lower()
    for record in records:
      if (record.get("ids") or {}).get("doi", "").lower() == needle:
        return record
  if title:
    needle = _normalize_bib_title(title)
    for record in records:
      if needle and _normalize_bib_title(record.get("title") or "") == needle:
        return record
  return None


def _numeric_reference_map(path: str | None,
                           records: list[dict]) -> dict[str, dict]:
  if path is None:
    return {}
  items = _read_json(pathlib.Path(path), "references")
  if not isinstance(items, list):
    sys.exit("references JSON must be an ordered array")
  mapping = {}
  for index, item in enumerate(items, 1):
    record = _reference_record(item, records)
    if record is None:
      sys.exit(f"reference {index} does not match a corpus record")
    mapping[f"number:{index}"] = record
  return mapping


def load_source(workspace: pathlib.Path, paper_id: str):
  papers_dir = (pathlib.Path(workspace) / "papers").resolve()
  paper_dir = (papers_dir / sanitize_id(paper_id)).resolve()
  if not paper_dir.is_relative_to(papers_dir):
    return None
  for name, scope in (("fulltext.md", "fulltext"), ("abstract.md", "abstract")):
    path = paper_dir / name
    if path.exists():
      return path.read_text(encoding="utf-8"), scope
  return None


def _words_in(quote_words: set, word: str) -> bool:
  return (word in quote_words or word + "s" in quote_words
          or word.rstrip("s") in quote_words)


def _anchor_check(claim_norm: str, quote_norm: str) -> tuple[dict, bool]:
  quote_numbers = set(extract_numbers(quote_norm))
  quote_words = set(re.findall(r"[a-z]+", quote_norm))
  numbers = extract_numbers(claim_norm)
  words = extract_words(claim_norm)
  anchors = {
      "numbers_found": [n for n in numbers if n in quote_numbers],
      "numbers_missing": [n for n in numbers if n not in quote_numbers],
      "words_found": [w for w in words if _words_in(quote_words, w)],
      "words_missing": [w for w in words if not _words_in(quote_words, w)],
  }
  numbers_ok = not numbers or not anchors["numbers_missing"]
  return anchors, numbers_ok


def _title_of(source: str) -> str:
  lines = source.lstrip().splitlines()[:12] if source.strip() else []
  for index, line in enumerate(lines):
    stripped = line.strip()
    if stripped.startswith("#"):
      return normalize_text(stripped.lstrip("# "))
    if not stripped.startswith("**"):
      continue
    title_lines = [stripped.removeprefix("**")]
    if stripped.endswith("**") and len(stripped) > 4:
      return normalize_text(title_lines[0].removesuffix("**"))
    for continuation in lines[index + 1:index + 5]:
      title_lines.append(continuation.strip())
      if continuation.strip().endswith("**"):
        return normalize_text(" ".join(title_lines).removesuffix("**"))
    break
  return ""


def _load_normalized(workspace, paper_id: str, cache):
  """(raw, normalized, scope) for a paper, or None; memoized per run."""
  if cache is not None and paper_id in cache:
    return cache[paper_id]
  loaded = load_source(workspace, paper_id)
  entry = (loaded[0], normalize_text(loaded[0]), loaded[1]) if loaded else None
  if cache is not None:
    cache[paper_id] = entry
  return entry


def check_entry(entry: dict, workspace, source_cache=None) -> dict:
  result = {"claim": entry.get("claim"), "paper_id": entry.get("paper_id"),
            "citation": entry.get("citation"),
            "supporting_quote": entry.get("supporting_quote"),
            "status": None, "source_scope": None, "quote_match_ratio": None,
            "matched": None, "best_window": None, "quote_is_title": False,
            "context_risks": [], "anchors": None}
  loaded = _load_normalized(workspace, entry.get("paper_id") or "",
                            source_cache)
  if loaded is None:
    result["status"] = "source_missing"
    return result
  source_raw, source_norm, scope = loaded
  result["source_scope"] = scope
  quote_norm = normalize_text(entry.get("supporting_quote") or "")
  if not quote_norm:
    result["status"] = "no_quote"
    return result
  if (len(quote_norm) < _MIN_QUOTE_CHARS
      or len(quote_norm.split()) < _MIN_QUOTE_WORDS):
    result["status"] = "quote_too_short"
    return result
  match = find_quote(quote_norm, source_norm)
  result["quote_match_ratio"] = round(match["coverage"], 2)
  result["matched"] = match["method"]
  if match["method"] is None:
    result["status"] = "fabricated_quote"
    result["best_window"] = match["window"]
    return result
  anchors, numbers_ok = _anchor_check(
      normalize_text(entry.get("claim") or ""), quote_norm)
  result["anchors"] = anchors
  result["context_risks"] = _boundary_context_risks(
      source_norm, match["start"], match["end"])
  title = _title_of(source_raw)
  if title and find_quote(quote_norm, title)["method"] is not None:
    result["quote_is_title"] = True
    result["status"] = "needs_review"
    return result
  if not numbers_ok or result["context_risks"]:
    result["status"] = "needs_review"
  else:
    result["status"] = ("background" if entry.get("role") == "background"
                        else "verified")
  return result


_YEAR = r"(?:19|20)\d{2}[a-z]?"
_LOCATOR = r"(?:,\s*(?:pp?\.?\s*)?\d+(?:\s*[-\u2013\u2014]\s*\d+)?)?"
_PAREN_RE = re.compile(r"\((?P<body>[^()]*)\)")
_PAREN_AUTHOR_YEAR_RE = re.compile(
    rf"^(?P<author>.+),\s*(?P<year>{_YEAR}){_LOCATOR}$")
_SURNAME = (r"(?:(?:van|von|de|del|der|la|le|dos|da)\s+){0,2}"
            r"[A-Z][A-Za-z'\u2019-]+")
_NARRATIVE_RE = re.compile(
    rf"\b(?P<author>{_SURNAME}(?:\s+et\s+al\.?|"
    rf"\s+(?:and|&)\s+{_SURNAME})?)\s+"
    rf"\((?P<year>{_YEAR}){_LOCATOR}\)")
_NUMERIC_CITATION_RE = re.compile(
    r"\[(?P<body>\d+(?:\s*(?:,|[-\u2013\u2014])\s*\d+)*)\]")
_ABSTRACT_TAG_RE = re.compile(r"\[abstract-only\]", re.IGNORECASE)

_HARD_FAILS = ("needs_review", "source_missing", "no_quote", "quote_too_short",
               "fabricated_quote", "uncovered_claim")


def _author_key(author: str) -> str:
  author = author.lower().replace("&", " and ")
  return re.sub(r"[^a-z0-9]+", " ", author).strip()


def _valid_author_label(author: str) -> bool:
  """Distinguish citation names from prose such as `In the final sample`."""
  allowed_lower = _NAME_PARTICLES | {"and", "et", "al"}
  words = re.findall(r"[A-Za-z][A-Za-z'\u2019-]*", author)
  if not words:
    return False
  named = 0
  for word in words:
    clean = word.strip("-'\u2019")
    if clean.lower() in allowed_lower:
      continue
    if not clean[0].isupper():
      return False
    named += 1
  return named > 0


def _numeric_keys(body: str) -> list[str]:
  numbers = []
  for part in re.split(r"\s*,\s*", body):
    range_match = re.fullmatch(r"(\d+)\s*[-\u2013\u2014]\s*(\d+)", part)
    if range_match:
      start, end = map(int, range_match.groups())
      if end < start or end - start > 100:
        continue
      numbers.extend(range(start, end + 1))
    else:
      numbers.append(int(part))
  return [f"number:{number}" for number in numbers]


def _citation_records(text: str) -> list[dict]:
  """Return parsed citation identities and their spans.

  Parenthetical citations require an author/year comma, avoiding prose such
  as `(Data collected in 2020)`. APA page locators are accepted. Narrative
  and numeric citations normalize to the same keys used by claims.json.
  """
  records = []
  for match in _PAREN_RE.finditer(text):
    for part in match.group("body").split(";"):
      parsed = _PAREN_AUTHOR_YEAR_RE.fullmatch(part.strip())
      if not parsed or not _valid_author_label(parsed.group("author")):
        continue
      records.append({
          "key": f"author:{_author_key(parsed.group('author'))}:"
                 f"{parsed.group('year').lower()}",
          "start": match.start(), "end": match.end(),
      })
  for match in _NARRATIVE_RE.finditer(text):
    records.append({
        "key": f"author:{_author_key(match.group('author'))}:"
               f"{match.group('year').lower()}",
        "start": match.start(), "end": match.end(),
    })
  for match in _NUMERIC_CITATION_RE.finditer(text):
    for key in _numeric_keys(match.group("body")):
      records.append({"key": key, "start": match.start(), "end": match.end()})
  return records


def citation_keys(text: str) -> set[str]:
  """Parse a citation as rendered or as a compact `Author, year` value."""
  records = _citation_records(text)
  if not records and text.strip() and not text.lstrip().startswith("["):
    records = _citation_records(f"({text.strip()})")
  return {record["key"] for record in records}


def _strip_citations(sentence: str, records: list[dict]) -> str:
  spans = [(r["start"], r["end"]) for r in records]
  spans.extend((m.start(), m.end()) for m in _ABSTRACT_TAG_RE.finditer(sentence))
  for start, end in sorted(set(spans), reverse=True):
    sentence = sentence[:start] + sentence[end:]
  return sentence


def _claim_text_matches(claim_norm: str, sent_norm: str) -> bool:
  return bool(
      claim_norm and ((len(claim_norm) >= 30 and claim_norm in sent_norm)
                      or (len(sent_norm) >= 30 and sent_norm in claim_norm)
                      or difflib.SequenceMatcher(
                          None, claim_norm, sent_norm,
                          autojunk=False).ratio()
                      >= _COVERAGE_MATCH_THRESHOLD))


def _split_sentences(text: str) -> list[str]:
  marker = "\u0000"
  protected = re.sub(
      r"\b(?:et al|pp?|e\.g|i\.e)\.",
      lambda match: match.group().replace(".", marker), text,
      flags=re.IGNORECASE)
  return [sentence.replace(marker, ".") for sentence in
          re.split(r"(?<=[.!?])\s+", protected)]


def coverage_gaps(synthesis: str, claims: list) -> list:
  claim_data = [(normalize_text(c.get("claim") or ""),
                 citation_keys(c.get("citation") or ""))
                for c in claims]
  gaps = []
  for sentence in _split_sentences(synthesis):
    records = _citation_records(sentence)
    sentence_keys = {r["key"] for r in records}
    if not sentence_keys:
      continue
    sent_norm = normalize_text(_strip_citations(sentence, records))
    covered_keys = set()
    for claim_norm, claim_keys in claim_data:
      if _claim_text_matches(claim_norm, sent_norm):
        covered_keys.update(claim_keys & sentence_keys)
    if not sentence_keys.issubset(covered_keys):
      gaps.append(sentence.strip())
  return gaps


def validate_entries(entries) -> None:
  if not isinstance(entries, list) or not entries:
    sys.exit("claims.json must be a non-empty JSON array of objects")
  for index, entry in enumerate(entries):
    if not isinstance(entry, dict):
      sys.exit(f"claims.json entry {index} must be an object")
    role = entry.get("role", "evidence")
    if role not in ("evidence", "background"):
      sys.exit(f"claims.json entry {index} has invalid role {role!r}")
    required = ("claim", "paper_id", "citation", "supporting_quote")
    for field in required:
      if not isinstance(entry.get(field), str) or not entry[field].strip():
        sys.exit(f"claims.json entry {index} requires non-empty {field!r}")
    keys = citation_keys(entry["citation"])
    if len(keys) != 1:
      sys.exit(f"claims.json entry {index} citation must identify exactly "
               "one author-year or numeric citation")


def validate_citation_bindings(entries: list[dict], workspace,
                               references: str | None = None) -> None:
  """Bind every declared citation to trusted corpus/reference metadata."""
  records = _corpus_records(workspace)
  numeric = _numeric_reference_map(references, records)
  for index, entry in enumerate(entries):
    record = _record_for_paper_id(records, entry["paper_id"])
    if record is None:
      if load_source(workspace, entry["paper_id"]) is None:
        continue  # check_entry reports the existing source_missing hard failure
      sys.exit(f"claims.json entry {index} paper_id is absent from corpus.json")
    trusted_role = record.get("role")
    declared_role = entry.get("role", "evidence")
    if trusted_role in ("evidence", "background") and declared_role != trusted_role:
      sys.exit(f"claims.json entry {index} role does not match corpus.json")
    key = next(iter(citation_keys(entry["citation"])))
    if key.startswith("author:"):
      if not record.get("authors"):
        sys.exit(f"corpus metadata for {entry['paper_id']!r} has no authors; "
                 "re-run build_corpus.py on the saved search results")
      if not _author_year_binding_matches(key, record):
        sys.exit(f"claims.json entry {index} citation does not match its "
                 "paper_id's corpus author/year")
    elif key not in numeric:
      sys.exit(f"claims.json entry {index} uses numeric citation {key[7:]}; "
               "pass the ordered refs.json with --references")
    elif numeric[key].get("key") != record.get("key"):
      sys.exit(f"claims.json entry {index} numeric citation does not match "
               "its paper_id's corpus record")


def main(argv=None) -> int:
  parser = argparse.ArgumentParser(
      description="Verify claims' supporting quotes against cited sources.")
  parser.add_argument("--claims", required=True)
  parser.add_argument("--workspace", required=True)
  parser.add_argument("--synthesis")
  parser.add_argument("--references",
                      help="Ordered refs.json; required for numeric citations")
  args = parser.parse_args(argv)

  try:
    entries = json.loads(pathlib.Path(args.claims).read_text(encoding="utf-8"))
  except (OSError, json.JSONDecodeError) as err:
    sys.exit(f"Cannot read claims file {args.claims}: {err}")
  validate_entries(entries)
  validate_citation_bindings(entries, args.workspace, args.references)

  source_cache = {}
  results = [check_entry(e, args.workspace, source_cache) for e in entries]

  coverage_checked = args.synthesis is not None
  if coverage_checked:
    try:
      synthesis = pathlib.Path(args.synthesis).read_text(encoding="utf-8")
    except OSError as err:
      sys.exit(f"Cannot read synthesis file {args.synthesis}: {err}")
    if not synthesis.strip():
      sys.exit("synthesis file must not be empty")
    if not _citation_records(synthesis):
      sys.exit("synthesis file contains no supported citation identities")
    for sentence in coverage_gaps(synthesis, entries):
      results.append({"claim": sentence, "paper_id": None,
                      "citation": None,
                      "supporting_quote": None, "status": "uncovered_claim",
                      "source_scope": None, "quote_match_ratio": None,
                      "matched": None, "best_window": None,
                      "quote_is_title": False, "context_risks": [],
                      "anchors": None})

  tally = collections.Counter(r["status"] for r in results)
  counts = {s: tally[s] for s in
            ("verified", "needs_review", "background", "fabricated_quote",
             "uncovered_claim", "source_missing", "no_quote",
             "quote_too_short")}
  abstract_verified = sum(1 for r in results if r["status"] == "verified"
                          and r["source_scope"] == "abstract")
  print(json.dumps({"total": len(results), **counts,
                    "coverage_checked": coverage_checked,
                    "results": results}, indent=2))
  unresolved = (counts["source_missing"] + counts["no_quote"]
                + counts["quote_too_short"])
  summary = (f"Claims: {counts['verified']} verified, "
             f"{counts['needs_review']} needs review, "
             f"{counts['background']} background, "
             f"{counts['fabricated_quote']} fabricated, "
             f"{counts['uncovered_claim']} uncovered (of {len(results)}); "
             f"{abstract_verified} verified only against an abstract")
  if unresolved:
    summary += f"; {unresolved} unresolved source/quote errors"
  print(summary, file=sys.stderr)
  return 1 if any(counts[s] for s in _HARD_FAILS) else 0


if __name__ == "__main__":
  sys.exit(main())
