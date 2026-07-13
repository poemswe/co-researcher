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

The agent supplies claims.json entries {claim, paper_id, supporting_quote,
role?}; this gate proves the quote exists in papers/{paper_id}/fulltext.md
(or abstract.md), flags quotes missing the claim's numbers, and — given
--synthesis — hard-fails any cited sentence with no matching claim entry,
so the gate cannot be starved of input. The match metric is coverage:
matched characters over quote length, never SequenceMatcher.ratio() of
quote against a whole document.

Exit 0 only when no claim is source_missing, no_quote, quote_too_short,
fabricated_quote, or uncovered_claim.
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
  wlen = qlen + step
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


def find_quote(quote: str, source: str) -> dict:
  """Locate the quote in the source: exact, fuzzy window, or per-sentence.

  Per-sentence fallback accepts a multi-sentence quote only when its sentences
  match in source order within 3x the quote's length — generous enough for one
  mid-quote PDF artifact (a page header, caption), tight enough to reject
  sentences stitched from distant sections.
  """
  idx = source.find(quote)
  if idx != -1 and _numbers_grounded(quote, source, lambda qs, qe: idx + qs):
    return {"coverage": 1.0, "window": quote, "method": "exact", "start": idx}
  cov, window, start = _best_window(quote, source)
  if cov >= _QUOTE_MATCH_THRESHOLD and _numbers_grounded(
      quote, source, _window_locator(quote, window, start)):
    return {"coverage": cov, "window": window, "method": "fuzzy",
            "start": start}
  sentences = [s for s in re.split(r"(?<=[.!?])\s+", quote) if s]
  if len(sentences) >= 2 and all(len(s) >= 20 for s in sentences):
    per = [find_quote(s, source) for s in sentences]
    if all(p["method"] is not None for p in per):
      starts = [p["start"] for p in per]
      ends = [st + len(s) for st, s in zip(starts, sentences)]
      span = max(ends) - min(starts)
      if starts == sorted(starts) and span <= 3 * len(quote):
        worst = min(per, key=lambda p: p["coverage"])
        return {"coverage": worst["coverage"], "window": worst["window"],
                "method": "per_sentence", "start": min(starts)}
  return {"coverage": cov, "window": window, "method": None, "start": start}


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
  first = source.lstrip().splitlines()[0] if source.strip() else ""
  return normalize_text(first.lstrip("# ")) if first.startswith("#") else ""


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
            "supporting_quote": entry.get("supporting_quote"),
            "status": None, "source_scope": None, "quote_match_ratio": None,
            "matched": None, "best_window": None, "quote_is_title": False,
            "anchors": None}
  if entry.get("role") == "background":
    result["status"] = "background"
    return result
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
  title = _title_of(source_raw)
  if title and find_quote(quote_norm, title)["method"] is not None:
    result["quote_is_title"] = True
    result["status"] = "needs_review"
    return result
  result["status"] = "verified" if numbers_ok else "needs_review"
  return result


_CITATION_RE = re.compile(
    r"\((?:[a-z]+ ){0,2}[A-Z][^()]{0,60}\b(?:19|20)\d{2}[a-z]?\)"
    r"|\b[A-Z][a-z]+(?:\s+et al\.?)?\s+\((?:19|20)\d{2}[a-z]?\)"
    r"|\[\d+\]|\[abstract-only\]")

_HARD_FAILS = ("source_missing", "no_quote", "quote_too_short",
               "fabricated_quote", "uncovered_claim")


def coverage_gaps(synthesis: str, claims: list) -> list:
  evidence = [c for c in claims if c.get("role") != "background"]
  claim_norms = [normalize_text(c.get("claim") or "") for c in evidence]
  paper_ids = {c.get("paper_id") or "" for c in evidence}
  gaps = []
  for sentence in re.split(r"(?<!et al\.)(?<=[.!?])\s+", synthesis):
    cited = bool(_CITATION_RE.search(sentence)) or any(
        pid and re.search(rf"(?<![A-Za-z0-9]){re.escape(pid)}(?![A-Za-z0-9])",
                          sentence)
        for pid in paper_ids)
    if not cited:
      continue
    sent_norm = normalize_text(_CITATION_RE.sub("", sentence))
    matched = any(
        cn and ((len(cn) >= 30 and cn in sent_norm)
                or (len(sent_norm) >= 30 and sent_norm in cn)
                or difflib.SequenceMatcher(
                    None, cn, sent_norm,
                    autojunk=False).ratio() >= _COVERAGE_MATCH_THRESHOLD)
        for cn in claim_norms)
    if not matched:
      gaps.append(sentence.strip())
  return gaps


def main(argv=None) -> int:
  parser = argparse.ArgumentParser(
      description="Verify claims' supporting quotes against cited sources.")
  parser.add_argument("--claims", required=True)
  parser.add_argument("--workspace", required=True)
  parser.add_argument("--synthesis")
  args = parser.parse_args(argv)

  try:
    entries = json.loads(pathlib.Path(args.claims).read_text(encoding="utf-8"))
  except (OSError, json.JSONDecodeError) as err:
    sys.exit(f"Cannot read claims file {args.claims}: {err}")
  if not isinstance(entries, list) or not all(
      isinstance(e, dict) for e in entries):
    sys.exit("claims.json must be a JSON array of objects")

  source_cache = {}
  results = [check_entry(e, args.workspace, source_cache) for e in entries]

  coverage_checked = args.synthesis is not None
  if coverage_checked:
    synthesis = pathlib.Path(args.synthesis).read_text(encoding="utf-8")
    for sentence in coverage_gaps(synthesis, entries):
      results.append({"claim": sentence, "paper_id": None,
                      "supporting_quote": None, "status": "uncovered_claim",
                      "source_scope": None, "quote_match_ratio": None,
                      "matched": None, "best_window": None,
                      "quote_is_title": False, "anchors": None})

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
