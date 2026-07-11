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
    "–": "-", "—": "-", "­": "",
})


def normalize_text(text: str) -> str:
  text = unicodedata.normalize("NFKC", text).translate(_CHAR_MAP)
  text = re.sub(r"(\w)-\s+(\w)", r"\1\2", text)
  return re.sub(r"\s+", " ", text.lower()).strip()


def _coverage(matcher: difflib.SequenceMatcher, quote_len: int) -> float:
  matched = sum(b.size for b in matcher.get_matching_blocks())
  return matched / quote_len if quote_len else 0.0


def _best_window(quote: str, source: str) -> tuple[float, str]:
  qlen = len(quote)
  step = max(1, qlen // 2)
  wlen = qlen + step
  matcher = difflib.SequenceMatcher(autojunk=False)
  matcher.set_seq2(quote)
  prefilter = 2 * _QUOTE_MATCH_THRESHOLD * qlen / (wlen + qlen)
  best_cov, best_win = 0.0, source[:wlen]
  for start in range(0, max(1, len(source) - qlen + 1), step):
    window = source[start:start + wlen]
    matcher.set_seq1(window)
    if matcher.real_quick_ratio() < prefilter:
      continue
    if matcher.quick_ratio() < prefilter:
      continue
    cov = _coverage(matcher, qlen)
    if cov > best_cov:
      best_cov, best_win = cov, window
  return best_cov, best_win


def _numbers_grounded(quote: str, window: str) -> bool:
  quote_numbers = extract_numbers(quote)
  if not quote_numbers:
    return True
  window_numbers = set(extract_numbers(window))
  return all(n in window_numbers for n in quote_numbers)


def find_quote(quote: str, source: str) -> dict:
  if quote in source:
    return {"coverage": 1.0, "window": quote, "method": "exact"}
  cov, window = _best_window(quote, source)
  if cov >= _QUOTE_MATCH_THRESHOLD:
    if _numbers_grounded(quote, window):
      return {"coverage": cov, "window": window, "method": "fuzzy"}
    return {"coverage": cov, "window": window, "method": None}
  sentences = [s for s in re.split(r"(?<=[.!?])\s+", quote) if s]
  if len(sentences) >= 2 and all(len(s) >= 20 for s in sentences):
    per = [find_quote(s, source) if s not in source else
           {"coverage": 1.0, "window": s} for s in sentences]
    worst_idx = min(range(len(per)), key=lambda i: per[i]["coverage"])
    worst = per[worst_idx]["coverage"]
    grounded = all(_numbers_grounded(s, p["window"])
                   for s, p in zip(sentences, per))
    if worst >= _QUOTE_MATCH_THRESHOLD and grounded:
      return {"coverage": worst, "window": per[worst_idx]["window"],
              "method": "per_sentence"}
  return {"coverage": cov, "window": window, "method": None}


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

_NUMBER_RE = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")


def extract_numbers(text: str) -> list[str]:
  numbers = []
  for tok in _NUMBER_RE.findall(text):
    plain = tok.replace(",", "")
    if len(plain) == 4 and plain.isdigit() and 1900 <= int(plain) <= 2099:
      continue
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


def _anchor_check(claim: str, quote_norm: str) -> tuple[dict, bool]:
  quote_numbers = set(extract_numbers(quote_norm))
  quote_words = set(re.findall(r"[a-z]+", quote_norm))
  numbers = extract_numbers(normalize_text(claim))
  words = extract_words(claim)
  anchors = {
      "numbers_found": [n for n in numbers if n in quote_numbers],
      "numbers_missing": [n for n in numbers if n not in quote_numbers],
      "words_found": [w for w in words if _words_in(quote_words, w)],
      "words_missing": [w for w in words if not _words_in(quote_words, w)],
  }
  numbers_ok = not numbers or bool(anchors["numbers_found"])
  return anchors, numbers_ok


def _title_of(source: str) -> str:
  first = source.lstrip().splitlines()[0] if source.strip() else ""
  return normalize_text(first.lstrip("# ")) if first.startswith("#") else ""


def check_entry(entry: dict, workspace) -> dict:
  result = {"claim": entry.get("claim"), "paper_id": entry.get("paper_id"),
            "supporting_quote": entry.get("supporting_quote"),
            "status": None, "source_scope": None, "quote_match_ratio": None,
            "matched": None, "best_window": None, "quote_is_title": False,
            "anchors": None}
  if entry.get("role") == "background":
    result["status"] = "background"
    return result
  loaded = load_source(workspace, entry.get("paper_id") or "")
  if loaded is None:
    result["status"] = "source_missing"
    return result
  source_raw, scope = loaded
  result["source_scope"] = scope
  quote_norm = normalize_text(entry.get("supporting_quote") or "")
  if not quote_norm:
    result["status"] = "no_quote"
    return result
  if (len(quote_norm) < _MIN_QUOTE_CHARS
      or len(quote_norm.split()) < _MIN_QUOTE_WORDS):
    result["status"] = "quote_too_short"
    return result
  source_norm = normalize_text(source_raw)
  match = find_quote(quote_norm, source_norm)
  result["quote_match_ratio"] = round(match["coverage"], 2)
  result["matched"] = match["method"]
  if match["method"] is None:
    result["status"] = "fabricated_quote"
    result["best_window"] = match["window"]
    return result
  anchors, numbers_ok = _anchor_check(entry.get("claim") or "", quote_norm)
  result["anchors"] = anchors
  title = _title_of(source_raw) if scope == "abstract" else ""
  if title and find_quote(quote_norm, title)["method"] is not None:
    result["quote_is_title"] = True
    result["status"] = "needs_review"
    return result
  result["status"] = "verified" if numbers_ok else "needs_review"
  return result


_CITATION_RE = re.compile(
    r"\((?:[a-z]+ ){0,2}[A-Z][^()]{0,60}\b(?:19|20)\d{2}\)"
    r"|\[\d+\]|\[abstract-only\]")

_HARD_FAILS = ("source_missing", "no_quote", "quote_too_short",
               "fabricated_quote", "uncovered_claim")


def coverage_gaps(synthesis: str, claims: list) -> list:
  claim_norms = [normalize_text(c.get("claim") or "") for c in claims]
  paper_ids = {c.get("paper_id") or "" for c in claims}
  gaps = []
  for sentence in re.split(r"(?<=[.!?])\s+", synthesis):
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

  results = [check_entry(e, args.workspace) for e in entries]

  coverage_checked = args.synthesis is not None
  if coverage_checked:
    synthesis = pathlib.Path(args.synthesis).read_text(encoding="utf-8")
    for sentence in coverage_gaps(synthesis, entries):
      results.append({"claim": sentence, "paper_id": None,
                      "supporting_quote": None, "status": "uncovered_claim",
                      "source_scope": None, "quote_match_ratio": None,
                      "matched": None, "best_window": None,
                      "quote_is_title": False, "anchors": None})

  counts = {s: sum(1 for r in results if r["status"] == s)
            for s in ("verified", "needs_review", "background",
                      "fabricated_quote", "uncovered_claim",
                      "source_missing", "no_quote", "quote_too_short")}
  abstract_verified = sum(1 for r in results if r["status"] == "verified"
                          and r["source_scope"] == "abstract")
  print(json.dumps({"total": len(results), **counts,
                    "coverage_checked": coverage_checked,
                    "results": results}, indent=2))
  print(f"Claims: {counts['verified']} verified, "
        f"{counts['needs_review']} needs review, "
        f"{counts['background']} background, "
        f"{counts['fabricated_quote']} fabricated, "
        f"{counts['uncovered_claim']} uncovered (of {len(results)}); "
        f"{abstract_verified} verified only against an abstract",
        file=sys.stderr)
  return 1 if any(counts[s] for s in _HARD_FAILS) else 0


if __name__ == "__main__":
  sys.exit(main())
