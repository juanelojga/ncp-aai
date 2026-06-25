import subprocess
from pathlib import Path

import markdown
from bs4 import BeautifulSoup

from ncp_aai.ingestion.normalize import DocumentSegment, normalize_text

SUPPORTED_EXTENSIONS = {".pdf", ".md", ".markdown", ".txt", ".html", ".htm"}


def read_document(path: Path) -> list[DocumentSegment]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return read_pdf(path)
    if suffix in {".md", ".markdown"}:
        return read_markdown(path)
    if suffix == ".txt":
        return read_text(path)
    if suffix in {".html", ".htm"}:
        return read_html(path)
    msg = f"Unsupported file type: {suffix}"
    raise ValueError(msg)


def read_text(path: Path) -> list[DocumentSegment]:
    return [
        DocumentSegment(
            text=normalize_text(path.read_text(encoding="utf-8")),
            section=path.stem,
        )
    ]


def read_markdown(path: Path) -> list[DocumentSegment]:
    text = path.read_text(encoding="utf-8")
    segments: list[DocumentSegment] = []
    current_heading = path.stem
    current_lines: list[str] = []

    for line in text.splitlines():
        if line.startswith("#"):
            if current_lines:
                segments.append(
                    DocumentSegment(
                        text=normalize_text("\n".join(current_lines)),
                        section=current_heading,
                    )
                )
                current_lines = []
            current_heading = line.lstrip("#").strip() or path.stem
        current_lines.append(line)

    if current_lines:
        segments.append(
            DocumentSegment(text=normalize_text("\n".join(current_lines)), section=current_heading)
        )
    return [segment for segment in segments if segment.text]


def read_html(path: Path) -> list[DocumentSegment]:
    html = path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    title = soup.title.string.strip() if soup.title and soup.title.string else path.stem
    body = soup.get_text("\n")
    return [DocumentSegment(text=normalize_text(body), section=title)]


def read_pdf(path: Path) -> list[DocumentSegment]:
    try:
        import fitz  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        return _read_pdf_with_pdftotext(path)

    segments: list[DocumentSegment] = []
    with fitz.open(path) as doc:
        for page_index, page in enumerate(doc, start=1):
            text = normalize_text(page.get_text("text"))
            if text:
                segments.append(
                    DocumentSegment(text=text, page=page_index, section=f"Page {page_index}")
                )
    return segments


def _read_pdf_with_pdftotext(path: Path) -> list[DocumentSegment]:
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        msg = "PDF ingestion requires PyMuPDF or the pdftotext command"
        raise RuntimeError(msg) from exc

    # pdftotext separates pages with form-feed characters.
    segments: list[DocumentSegment] = []
    for page_index, page_text in enumerate(result.stdout.split("\f"), start=1):
        text = normalize_text(page_text)
        if text:
            segments.append(
                DocumentSegment(text=text, page=page_index, section=f"Page {page_index}")
            )
    return segments


def markdown_to_text(markdown_text: str) -> str:
    html = markdown.markdown(markdown_text)
    soup = BeautifulSoup(html, "html.parser")
    return normalize_text(soup.get_text("\n"))
