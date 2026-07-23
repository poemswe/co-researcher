from __future__ import annotations

import dataclasses
import re
import unicodedata
from collections import Counter

MAX_NUMERIC_RANGE_SPAN = 100

_YEAR = r"(?:19|20)\d{2}[a-z]?"
_LOCATOR = r"(?:,\s*(?:pp?\.?\s*)?\d+(?:\s*[-\u2013\u2014]\s*\d+)?)?"
_PAREN_RE = re.compile(r"\((?P<body>[^()]*)\)")
_PAREN_AUTHOR_YEAR_RE = re.compile(
    rf"^(?P<author>.+),\s*(?P<year>{_YEAR}){_LOCATOR}$")
_LETTER = r"[^\W\d_]"
_NAME_TOKEN = rf"{_LETTER}+(?:['’\-]{_LETTER}+)*"
_NAME_TOKEN_RE = re.compile(_NAME_TOKEN, re.UNICODE)
_PARTICLE = r"(?i:al|da|de|del|della|den|der|di|dos|du|la|le|van|von)"
_SURNAME = (
    rf"(?:{_PARTICLE}\s+){{0,3}}"
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
    "al da de del della den der di dos du la le van von".split())
_AUTHOR_CONTROL_WORDS = _NAME_PARTICLES | {"and", "et", "al"}
_INTERNAL_NAME_PUNCTUATION = frozenset({"'", "’", "-"})


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


def _is_unicode_letter(character: str) -> bool:
  return unicodedata.category(character).startswith("L")


def _is_combining_mark(character: str) -> bool:
  return unicodedata.category(character).startswith("M")


def _valid_author_characters(author: str) -> bool:
  if not author:
    return False
  for index, character in enumerate(author):
    if _is_unicode_letter(character):
      continue
    if _is_combining_mark(character):
      if index == 0 or not (
          _is_unicode_letter(author[index - 1])
          or _is_combining_mark(author[index - 1])
      ):
        return False
      continue
    if character.isspace():
      continue
    if character in _INTERNAL_NAME_PUNCTUATION:
      if index == 0 or index == len(author) - 1:
        return False
      if not (
          _is_unicode_letter(author[index - 1])
          or _is_combining_mark(author[index - 1])
      ):
        return False
      if not _is_unicode_letter(author[index + 1]):
        return False
      continue
    if character == "&":
      if index == 0 or index == len(author) - 1:
        return False
      continue
    if character == ".":
      stripped = author.rstrip()
      if (
          index != len(stripped) - 1
          or not stripped.casefold().endswith("et al.")
      ):
        return False
      continue
    return False
  return True


def _valid_author_label(author: str) -> bool:
  if not _valid_author_characters(author):
    return False
  tokens = _name_tokens(author)
  if not tokens:
    return False
  named = 0
  for token in tokens:
    if token.casefold() in _AUTHOR_CONTROL_WORDS:
      continue
    components = re.split(r"['’\-]+", token)
    component_is_name = False
    for component in components:
      if component.casefold() in _NAME_PARTICLES:
        continue
      first = next(
          (char for char in component if _is_unicode_letter(char)),
          None,
      )
      if first is None or first.islower():
        return False
      component_is_name = True
    if not component_is_name:
      continue
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
      span = end - start
      if span < 0:
        raise CoverageEnumerationError(
            f"numeric citation range descends: {start}-{end}"
        )
      if span > MAX_NUMERIC_RANGE_SPAN:
        raise CoverageEnumerationError(
            "numeric citation range span "
            f"{span} exceeds maximum {MAX_NUMERIC_RANGE_SPAN}"
        )
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
    author_start, author_end = match.span("author")
    if not spans or author_start == author_end:
      continue
    original_author = sentence[
        spans[author_start][0]:spans[author_end - 1][1]
    ]
    if _valid_author_label(original_author):
      keys.add(
          f"author:{_author_key(original_author)}:"
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
