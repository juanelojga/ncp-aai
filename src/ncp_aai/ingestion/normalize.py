import hashlib
import re
from dataclasses import dataclass

WHITESPACE_RE = re.compile(r"[ \t]+")
BLANK_LINES_RE = re.compile(r"\n{3,}")


@dataclass(frozen=True)
class DocumentSegment:
    text: str
    page: int | None = None
    section: str | None = None


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(WHITESPACE_RE.sub(" ", line).strip() for line in text.splitlines())
    return BLANK_LINES_RE.sub("\n\n", text).strip()


def hash_text(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def segment_text(segments: list[DocumentSegment]) -> str:
    return "\n\n".join(segment.text for segment in segments if segment.text.strip())
