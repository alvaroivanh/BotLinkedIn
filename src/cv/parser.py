from pathlib import Path

import pdfplumber


def extract_text_pdfplumber(pdf_path: Path) -> str:
    """Extract text from PDF using pdfplumber (best for structured/tabular resumes)."""
    text_parts: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n\n".join(text_parts)


def extract_text_pymupdf(pdf_path: Path) -> str:
    """Fallback: extract text using PyMuPDF (better for image-heavy PDFs)."""
    import fitz

    doc = fitz.open(pdf_path)
    text_parts: list[str] = []
    for page in doc:
        text_parts.append(page.get_text())
    doc.close()
    return "\n\n".join(text_parts)


def extract_text(pdf_path: Path) -> str:
    """Extract text from a PDF resume, trying pdfplumber first, PyMuPDF as fallback."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    text = extract_text_pdfplumber(pdf_path)
    if len(text.strip()) < 50:
        text = extract_text_pymupdf(pdf_path)

    if not text.strip():
        raise ValueError(f"Could not extract text from PDF: {pdf_path}")

    return text.strip()
