import pathlib
import sys

import pytest

_SCRIPTS = (pathlib.Path(__file__).resolve().parent.parent
            / "skills/literature-review/scripts")
sys.path.insert(0, str(_SCRIPTS))

import http_client  # noqa: E402
import zotero_local  # noqa: E402

_COLLECTIONS = [
    {"key": "AAAA1111", "data": {"key": "AAAA1111", "name": "Sleep review"}},
    {"key": "BBBB2222", "data": {"key": "BBBB2222", "name": "Methods"}},
    {"key": "CCCC3333", "data": {"key": "CCCC3333", "name": "Methods"}},
]


def _serve(monkeypatch, routes):
  requested = []

  def answer(path, **kwargs):
    requested.append(path)
    value = routes[path]
    if isinstance(value, Exception):
      raise value
    return value

  monkeypatch.setattr(zotero_local._CLIENT, "fetch_json", answer)
  monkeypatch.setattr(zotero_local._CLIENT, "fetch_text", answer)
  return requested


def test_client_only_talks_to_localhost():
  assert zotero_local._CLIENT.hostname == "localhost"
  with pytest.raises(ValueError):
    zotero_local._CLIENT._resolve_url("https://api.zotero.org/users/0/items")


def test_collection_key_accepts_a_key_or_a_unique_name(monkeypatch):
  _serve(monkeypatch, {"collections": _COLLECTIONS})
  assert zotero_local.collection_key("AAAA1111") == "AAAA1111"
  assert zotero_local.collection_key("Sleep review") == "AAAA1111"


@pytest.mark.parametrize("name, message", [
    ("Nope", "no Zotero collection named 'Nope'"),
    ("Methods", "2 Zotero collections are named 'Methods'"),
])
def test_collection_key_rejects_missing_or_ambiguous_names(
    monkeypatch, name, message):
  _serve(monkeypatch, {"collections": _COLLECTIONS})
  with pytest.raises(ValueError, match=message):
    zotero_local.collection_key(name)


def test_subcollection_walk_terminates_on_repeats(monkeypatch):
  _serve(monkeypatch, {
      "collections/AAAA1111/collections": [{"key": "BBBB2222"}],
      "collections/BBBB2222/collections": [{"key": "AAAA1111"},
                                           {"key": "CCCC3333"}],
      "collections/CCCC3333/collections": [],
  })
  assert zotero_local.subcollection_keys("AAAA1111") == [
      "AAAA1111", "BBBB2222", "CCCC3333"]


def test_collection_items_reads_csl_and_keys(monkeypatch):
  _serve(monkeypatch, {"collections/AAAA1111/items/top?format=csljson": {
      "items": [{"id": "12345/ITEM0001", "title": "A"}]}})
  assert zotero_local.collection_items("AAAA1111") == [
      ("ITEM0001", {"id": "12345/ITEM0001", "title": "A"})]


def test_pdf_attachment_and_path(monkeypatch, tmp_path):
  pdf = tmp_path / "a b.pdf"
  _serve(monkeypatch, {
      "items/ITEM0001/children": [
          {"key": "NOTE0001", "data": {"itemType": "note"}},
          {"key": "ATT00001", "data": {"itemType": "attachment",
                                       "contentType": "application/pdf"}}],
      "items/ATT00001/file/view/url": pdf.as_uri() + "\n",
      "items/ATT00001": {"data": {"parentItem": "ITEM0001"}},
  })
  assert zotero_local.pdf_attachment("ITEM0001") == "ATT00001"
  assert zotero_local.attachment_path("ATT00001") == pdf
  assert zotero_local.attachment_parent("ATT00001") == "ITEM0001"


def test_missing_attachment_file_is_none(monkeypatch):
  _serve(monkeypatch, {"items/ATT00001/file/view/url":
                       http_client.HttpError("gone", status_code=404)})
  assert zotero_local.attachment_path("ATT00001") is None


@pytest.mark.parametrize("error, message", [
    (http_client.HttpError("no", status_code=403),
     "Allow other applications on this computer to communicate with Zotero"),
    (http_client.HttpError("refused"), "Zotero is not reachable"),
])
def test_unavailable_zotero_names_the_fix(monkeypatch, error, message):
  _serve(monkeypatch, {"collections": error})
  with pytest.raises(zotero_local.ZoteroUnavailable, match=message):
    zotero_local.collection_names()


def test_requests_are_relative_to_the_local_api(monkeypatch):
  requested = _serve(monkeypatch, {"collections": _COLLECTIONS})
  zotero_local.collection_key("Sleep review")
  assert all("://" not in path for path in requested)


def test_item_title_reads_the_item_record(monkeypatch):
  _serve(monkeypatch, {"items/ITEM0001": {"data": {"title": "Real Paper"}},
                       "items/GONE0001": http_client.HttpError(
                           "gone", status_code=404)})
  assert zotero_local.item_title("ITEM0001") == "Real Paper"
  assert zotero_local.item_title("GONE0001") is None
