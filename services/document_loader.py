"""
Document loader — extracts plain text from uploaded files.
Supports: .txt, .pdf, .docx
"""

import io
from typing import Union, Tuple, List

from streamlit.runtime.uploaded_file_manager import UploadedFile


def extract_pages(file_bytes: bytes, filename: str) -> List[str]:
    ext = filename.lower().split(".")[-1]

    if ext == "txt":
        return _extract_txt_pages(file_bytes)
    elif ext == "pdf":
        return _extract_pdf_pages(file_bytes)
    elif ext in ("docx", "doc"):
        return _extract_docx_pages(file_bytes)
    else:
        raise ValueError(
            f"Unsupported file type: .{ext}  |  Supported: .txt, .pdf, .docx"
        )


def _extract_txt_pages(data: bytes, chars_per_page: int = 3000) -> List[str]:
    text = ""
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    
    if not text:
        raise ValueError("Could not decode .txt file with any known encoding.")

    # Split into rough "pages"
    return [text[i : i + chars_per_page] for i in range(0, len(text), chars_per_page)]


def _extract_pdf_pages(data: bytes) -> List[str]:
    try:
        from PyPDF2 import PdfReader
    except ImportError as exc:
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
    return pages


def _extract_docx_pages(data: bytes, paragraphs_per_page: int = 15) -> List[str]:
    try:
        from docx import Document as DocxDocument
    except ImportError as exc:
        raise ImportError(
            "python-docx is required to read .docx files. Run: pip install python-docx"
        ) from exc

    doc = DocxDocument(io.BytesIO(data))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    
    # Split paragraphs into rough pages
    pages = []
    for i in range(0, len(paragraphs), paragraphs_per_page):
        pages.append("\n".join(paragraphs[i : i + paragraphs_per_page]))
    
    return pages


def load_document(uploaded_file: Union[UploadedFile, None]) -> Tuple[List[str], int, int]:
    if uploaded_file is None:
        raise ValueError("No file was uploaded. Please upload a document first.")

    pages = extract_pages(uploaded_file.getvalue(), uploaded_file.name)
    full_text = "\n".join(pages)
    return pages, len(full_text.split()), len(full_text)
