import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://coresearcher.poemswe.com/"


class _Links(HTMLParser):
  def __init__(self):
    super().__init__()
    self.hrefs = []
    self.canonical = None

  def handle_starttag(self, tag, attrs):
    attrs = dict(attrs)
    if tag == "a" and attrs.get("href"):
      self.hrefs.append(attrs["href"])
    if tag == "link" and attrs.get("rel") == "canonical":
      self.canonical = attrs.get("href")


def _parse(path):
  parser = _Links()
  parser.feed(path.read_text(encoding="utf-8"))
  return parser


def _local_file(url):
  path = url.removeprefix(SITE)
  return ROOT / (path + "index.html" if path == "" or path.endswith("/") else path)


def _sitemap_urls():
  return re.findall(r"<loc>([^<]+)</loc>", (ROOT / "sitemap.xml").read_text())


def test_every_sitemap_url_is_a_published_file():
  for url in _sitemap_urls():
    assert url.startswith(SITE), url
    assert _local_file(url).is_file(), url


def test_sitemap_lists_the_paper():
  assert f"{SITE}paper/" in _sitemap_urls()


def test_html_pages_declare_their_own_canonical_url():
  for url in _sitemap_urls():
    if url.endswith("/"):
      assert _parse(_local_file(url)).canonical == url


def test_home_and_evals_link_to_the_paper():
  for page in ("index.html", "evals/index.html"):
    assert "/paper/" in _parse(ROOT / page).hrefs, page


def test_paper_internal_links_resolve():
  for href in _parse(ROOT / "paper/index.html").hrefs:
    if href.startswith("/") and not href.startswith("//"):
      target = ROOT / href.lstrip("/").split("#")[0]
      assert target.is_file() or (target / "index.html").is_file(), href
