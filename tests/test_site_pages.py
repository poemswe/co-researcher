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
    self.meta = {}

  def handle_starttag(self, tag, attrs):
    attrs = dict(attrs)
    if tag == "a" and attrs.get("href"):
      self.hrefs.append(attrs["href"])
    if tag == "link" and attrs.get("rel") == "canonical":
      self.canonical = attrs.get("href")
    if tag == "meta" and (attrs.get("property") or attrs.get("name")):
      self.meta[attrs.get("property") or attrs.get("name")] = attrs.get("content")


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


def test_sitemap_lists_the_write_up():
  assert f"{SITE}paper/write-up/" in _sitemap_urls()


def test_summary_and_write_up_link_to_each_other():
  assert "/paper/write-up/" in _parse(ROOT / "paper/index.html").hrefs
  assert "/paper/" in _parse(ROOT / "paper/write-up/index.html").hrefs


def test_report_internal_links_resolve():
  for page in ("paper/index.html", "paper/write-up/index.html"):
    for href in _parse(ROOT / page).hrefs:
      if href.startswith("/") and not href.startswith("//"):
        target = ROOT / href.lstrip("/").split("#")[0]
        assert target.is_file() or (target / "index.html").is_file(), (page, href)


def test_html_pages_share_the_site_card():
  for url in _sitemap_urls():
    if url.endswith("/"):
      meta = _parse(_local_file(url)).meta
      assert meta["og:image"] == f"{SITE}og-image.png", url
      assert meta["twitter:image"] == f"{SITE}og-image.png", url
      assert meta["twitter:card"] == "summary_large_image", url
  assert _local_file(f"{SITE}og-image.png").stat().st_size < 1_000_000
