import pymupdf


def make_pdf(path, text):
  doc = pymupdf.open()
  page = doc.new_page()
  if text:
    page.insert_text((72, 72), text)
  path.parent.mkdir(parents=True, exist_ok=True)
  doc.save(path)
  return path
