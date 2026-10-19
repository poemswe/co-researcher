"""Read-only client for the Zotero 7 local API on this machine.

Only http://localhost:23119 is contacted. Reads need no key once Settings >
Advanced > "Allow other applications on this computer to communicate with
Zotero" is enabled.
"""

import pathlib
import urllib.parse
import urllib.request

import http_client

BASE_URL = "http://localhost:23119/api/users/0/"
_CLIENT = http_client.HttpClient(BASE_URL, qps=20.0, max_retries=0)
_DISABLED = ('Zotero refused the request. Enable Settings > Advanced > "Allow '
             'other applications on this computer to communicate with Zotero".')
_NOT_RUNNING = ("Zotero is not reachable at localhost:23119. Start Zotero 7, "
                "or export the collection to BibTeX or CSL JSON and use --file.")


class ZoteroUnavailable(RuntimeError):
  pass


def _get(path, *, text=False, missing_ok=False):
  try:
    if text:
      return _CLIENT.fetch_text(path)
    return _CLIENT.fetch_json(path)
  except http_client.HttpError as err:
    if missing_ok and err.status_code == 404:
      return None
    if err.status_code == 403:
      raise ZoteroUnavailable(_DISABLED) from err
    if err.status_code is None:
      raise ZoteroUnavailable(_NOT_RUNNING) from err
    raise ZoteroUnavailable(f"Zotero local API error: {err}") from err


def collection_names() -> dict[str, str]:
  return {c["key"]: c["data"]["name"] for c in _get("collections")}


def collection_key(name_or_key: str) -> str:
  names = collection_names()
  if name_or_key in names:
    return name_or_key
  named = sorted(key for key, name in names.items() if name == name_or_key)
  if len(named) == 1:
    return named[0]
  if not named:
    raise ValueError(f"no Zotero collection named {name_or_key!r}; "
                     f"collections: {sorted(names.values())}")
  raise ValueError(f"{len(named)} Zotero collections are named "
                   f"{name_or_key!r}; pass one key: {named}")


def subcollection_keys(key: str) -> list[str]:
  keys, pending = [], [key]
  while pending:
    current = pending.pop(0)
    if current in keys:
      continue
    keys.append(current)
    pending.extend(c["key"] for c in _get(f"collections/{current}/collections"))
  return keys


def collection_items(key: str) -> list[tuple[str, dict]]:
  data = _get(f"collections/{key}/items/top?format=csljson")
  items = data.get("items", []) if isinstance(data, dict) else data
  return [(str(item.get("id", "")).rsplit("/", 1)[-1], item) for item in items]


def pdf_attachment(item_key: str) -> str | None:
  for child in _get(f"items/{item_key}/children"):
    data = child.get("data") or {}
    if (data.get("itemType") == "attachment"
        and data.get("contentType") == "application/pdf"):
      return child["key"]
  return None


def attachment_parent(attachment_key: str) -> str | None:
  item = _get(f"items/{attachment_key}", missing_ok=True) or {}
  return (item.get("data") or {}).get("parentItem")


def item_title(item_key: str) -> str | None:
  item = _get(f"items/{item_key}", missing_ok=True) or {}
  return (item.get("data") or {}).get("title")


def attachment_path(attachment_key: str) -> pathlib.Path | None:
  url = _get(f"items/{attachment_key}/file/view/url", text=True, missing_ok=True)
  if not url:
    return None
  return pathlib.Path(urllib.request.url2pathname(
      urllib.parse.urlparse(url.strip()).path))
