"""Paper ingestion: .md/.txt directly, .pdf via optional pymupdf."""
from __future__ import annotations

from pathlib import Path

from .models import Paper

MAX_CHARS = 400_000  # reject rather than silently truncate


def load_paper(path: str) -> Paper:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"paper not found: {path}")
    warnings = []
    if p.suffix.lower() == ".pdf":
        try:
            import pymupdf
        except ImportError as e:
            raise RuntimeError("PDF input needs: pip install 'forensic-agent[pdf]'") from e
        with pymupdf.open(p) as doc:
            text = "\n\n".join(page.get_text() for page in doc)
        warnings.append("PDF text extraction: tables may be garbled")
    else:
        text = p.read_text(errors="replace")
    if not text.strip():
        raise ValueError(f"{path}: no extractable text (scanned PDF?)")
    if len(text) > MAX_CHARS:
        raise ValueError(f"{path}: {len(text)} chars exceeds limit of {MAX_CHARS}")
    return Paper(source=str(p), text=text, warnings=warnings)
