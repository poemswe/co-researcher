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


def find_quote(quote: str, source: str) -> dict:
  if quote in source:
    return {"coverage": 1.0, "window": quote, "method": "exact"}
  cov, window = _best_window(quote, source)
  if cov >= _QUOTE_MATCH_THRESHOLD:
    return {"coverage": cov, "window": window, "method": "fuzzy"}
  sentences = [s for s in re.split(r"(?<=[.!?])\s+", quote) if s]
  if len(sentences) >= 2 and all(len(s) >= 20 for s in sentences):
    per = [find_quote(s, source) if s not in source else
           {"coverage": 1.0, "window": s} for s in sentences]
    worst_idx = min(range(len(per)), key=lambda i: per[i]["coverage"])
    worst = per[worst_idx]["coverage"]
    if worst >= _QUOTE_MATCH_THRESHOLD:
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
