"""
Document loader — extracts plain text from uploaded files.
Supports: .txt, .pdf, .docx
"""

import io
from typing import Union, Tuple
from streamlit.runtime.uploaded_file_manager import UploadedFile


# ---------------------------------------------------------------------------
# Core extractor (no Streamlit dependency — can be unit tested)
# ---------------------------------------------------------------------------

def extract_text(file_bytes: bytes, filename: str) -> str:
    """
    Route a raw byte payload to the correct extractor based on file extension.

    Args:
        file_bytes : Raw bytes from the uploaded file.
        filename   : Original filename used to detect format.

    Returns:
        Plain-text string extracted from the document.

    Raises:
        ValueError: If the file format is unsupported.
    """
    ext = filename.lower().split(".")[-1]

    if ext == "txt":
        return _extract_txt(file_bytes)
    elif ext == "pdf":
        return _extract_pdf(file_bytes)
    elif ext in ("docx", "doc"):
        return _extract_docx(file_bytes)
    else:
        raise ValueError(
            f"Unsupported file type: .{ext}  |  Supported: .txt, .pdf, .docx"
        )


def _extract_txt(data: bytes) -> str:
    """Decode bytes as UTF-8 with fallback to latin-1."""
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not decode .txt file with any known encoding.")


def _extract_pdf(data: bytes) -> str:
    """Pull every text page from a PDF using PyPDF2."""
    try:
        from PyPDF2 import PdfReader
    except ImportError as exc:  # pragma: no cover — guard for dev without deps
        raise ImportError(
            "PyPDF2 is required to read PDF files. Run: pip install PyPDF2"
        ) from exc

    reader = PdfReader(io.BytesIO(data))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)

    if not pages:
        raise ValueError("PDF contains no extractable text (may be image-based).")
    return "\n\n".join(pages)


def _extract_docx(data: bytes) -> str:
    """Pull all paragraphs from a .docx file using python-docx."""
    try:
        from docx import Document as DocxDocument
    except ImportError as exc:
        raise ImportError(
            "python-docx is required to read .docx files. Run: pip install python-docx"
        ) from exc

    doc = DocxDocument(io.BytesIO(data))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


# ---------------------------------------------------------------------------
# Streamlit-friendly wrapper (uses st.session_state for progress feedback)
# ---------------------------------------------------------------------------

def load_document(uploaded_file: Union[UploadedFile, None]) -> Tuple[str, int, int]:
    """
    Convenience wrapper for use inside a Streamlit app.
    Handles the UploadedFile → bytes conversion and reports stats.

    Returns:
        Plain-text content of the document.

    Raises:
        ValueError: If no file is provided.
    """
    if uploaded_file is None:
        raise ValueError("No file was uploaded. Please upload a document first.")

    file_bytes = uploaded_file.getvalue()
    filename   = uploaded_file.name

    text = extract_text(file_bytes, filename)

    word_count = len(text.split())
    char_count = len(text)
    return text, word_count, char_count
