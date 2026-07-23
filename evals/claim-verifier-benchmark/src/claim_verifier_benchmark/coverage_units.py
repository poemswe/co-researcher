from __future__ import annotations

import dataclasses
import re
import unicodedata
from collections import Counter

_YEAR = r"(?:19|20)\d{2}[a-z]?"
_LOCATOR = r"(?:,\s*(?:pp?\.?\s*)?\d+(?:\s*[-\u2013\u2014]\s*\d+)?)?"
_PAREN_RE = re.compile(r"\((?P<body>[^()]*)\)")
_PAREN_AUTHOR_YEAR_RE = re.compile(
    rf"^(?P<author>.+),\s*(?P<year>{_YEAR}){_LOCATOR}$")
_LETTER = r"[^\W\d_]"
_NAME_TOKEN = rf"{_LETTER}+(?:['’\-]{_LETTER}+)*"
_NAME_TOKEN_RE = re.compile(_NAME_TOKEN, re.UNICODE)
_SURNAME = (
    r"(?:(?i:van|von|de|del|der|la|le|dos|da)\s+){0,2}"
    rf"{_NAME_TOKEN}"
)
_NARRATIVE_RE = re.compile(
    rf"\b(?P<author>{_SURNAME}(?:\s+et\s+al\.?|"
    rf"\s+(?:and|&)\s+{_SURNAME})?)\s+"
    rf"\((?P<year>{_YEAR}){_LOCATOR}\)")
_NUMERIC_RE = re.compile(
    r"\[(?P<body>\d+(?:\s*(?:,|[-\u2013\u2014])\s*\d+)*)\]")
_ABBREVIATION_RE = re.compile(
    r"\b(?:et al|pp?|e\.g|i\.e)\.", re.IGNORECASE)
_NAME_PARTICLES = frozenset(
    "al da de del della der di dos du la le van von".split())


class CoverageEnumerationError(ValueError):
  pass


@dataclasses.dataclass(frozen=True, slots=True)
class CoverageUnit:
  unit_id: str
  sentence_ordinal: int
  start: int
  end: int
  sentence: str
  citation_identity: str
  occurrence_ordinal: int


def _name_tokens(text: str) -> list[str]:
  return _NAME_TOKEN_RE.findall(unicodedata.normalize("NFKC", text))


def _author_key(author: str) -> str:
  folded = unicodedata.normalize("NFKC", author).casefold().replace(
      "&", " and ")
  pieces = [re.sub(r"['’\-]+", " ", token)
            for token in _name_tokens(folded)]
  return re.sub(r"\s+", " ", " ".join(pieces)).strip()


def _valid_author_label(author: str) -> bool:
  tokens = _name_tokens(author)
  if not tokens:
    return False
  named = 0
  for token in tokens:
    if token.casefold() in _NAME_PARTICLES | {"and", "et", "al"}:
      continue
    first = next(char for char in token if char.isalpha())
    if first.islower():
      return False
    named += 1
  return named > 0


def _nfkc_shadow(text: str) -> tuple[str, list[tuple[int, int]]]:
  pieces: list[str] = []
  spans: list[tuple[int, int]] = []
  start = 0
  for end in range(1, len(text) + 1):
    if end < len(text) and unicodedata.category(text[end]).startswith("M"):
      continue
    piece = unicodedata.normalize("NFKC", text[start:end])
    pieces.append(piece)
    spans.extend((start, end) for _ in piece)
    start = end
  return "".join(pieces), spans


def _numeric_keys(body: str) -> list[str]:
  numbers: list[int] = []
  for part in re.split(r"\s*,\s*", body):
    match = re.fullmatch(r"(\d+)\s*[-\u2013\u2014]\s*(\d+)", part)
    if match:
      start, end = map(int, match.groups())
      if end < start or end - start > 100:
        continue
      numbers.extend(range(start, end + 1))
    else:
      numbers.append(int(part))
  return [f"number:{number}" for number in numbers]


def _citation_keys(sentence: str) -> set[str]:
  keys: set[str] = set()
  for match in _PAREN_RE.finditer(sentence):
    for part in match.group("body").split(";"):
      parsed = _PAREN_AUTHOR_YEAR_RE.fullmatch(part.strip())
      if parsed and _valid_author_label(parsed.group("author")):
        keys.add(
            f"author:{_author_key(parsed.group('author'))}:"
            f"{parsed.group('year').lower()}")
  shadow, spans = _nfkc_shadow(sentence)
  for match in _NARRATIVE_RE.finditer(shadow):
    if spans and _valid_author_label(match.group("author")):
      keys.add(
          f"author:{_author_key(match.group('author'))}:"
          f"{match.group('year').lower()}")
  for match in _NUMERIC_RE.finditer(sentence):
    keys.update(_numeric_keys(match.group("body")))
  return keys


def _sentence_spans(text: str) -> list[tuple[int, int]]:
  shadow = list(text)
  for match in _ABBREVIATION_RE.finditer(text):
    for index in range(match.start(), match.end()):
      if shadow[index] == ".":
        shadow[index] = "\0"
  protected = "".join(shadow)
  spans: list[tuple[int, int]] = []
  start = 0
  for boundary in re.finditer(r"(?<=[.!?])\s+", protected):
    spans.append((start, boundary.start()))
    start = boundary.end()
  spans.append((start, len(text)))
  return spans


def enumerate_coverage_units(synthesis: str) -> tuple[CoverageUnit, ...]:
  if "\r" in synthesis:
    raise CoverageEnumerationError("synthesis must be LF-normalized")
  counters: Counter[tuple[str, str]] = Counter()
  units: list[CoverageUnit] = []
  for sentence_ordinal, (start, end) in enumerate(_sentence_spans(synthesis)):
    sentence = synthesis[start:end]
    for identity_index, identity in enumerate(sorted(_citation_keys(sentence))):
      key = (sentence, identity)
      counters[key] += 1
      units.append(CoverageUnit(
          unit_id=f"coverage:{sentence_ordinal}:{identity_index}",
          sentence_ordinal=sentence_ordinal,
          start=start,
          end=end,
          sentence=sentence,
          citation_identity=identity,
          occurrence_ordinal=counters[key],
      ))
  return tuple(units)
