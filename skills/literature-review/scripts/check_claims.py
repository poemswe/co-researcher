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
  if len(sentences) >= 2:
    per = [find_quote(s, source) if s not in source else
           {"coverage": 1.0} for s in sentences]
    worst = min(p["coverage"] for p in per)
    if worst >= _QUOTE_MATCH_THRESHOLD:
      return {"coverage": worst, "window": window, "method": "per_sentence"}
  return {"coverage": cov, "window": window, "method": None}
