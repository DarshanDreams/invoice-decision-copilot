import fitz  # PyMuPDF
from typing import Dict, Any


def extract_text_from_pdf(uploaded_file) -> Dict[str, Any]:
    """
    Extract text from an uploaded PDF file.

    Returns:
        {
            "success": bool,
            "text": str,
            "page_count": int,
            "character_count": int,
            "is_probably_scanned": bool,
            "error": str | None
        }
    """

    try:
        pdf_bytes = uploaded_file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        all_text = []

        for page_number, page in enumerate(doc, start=1):
            page_text = page.get_text("text")
            all_text.append(f"\n--- Page {page_number} ---\n{page_text}")

        full_text = "\n".join(all_text).strip()
        character_count = len(full_text)

        # If a PDF has almost no extractable text, it is probably scanned/image-based.
        is_probably_scanned = character_count < 50

        return {
            "success": True,
            "text": full_text,
            "page_count": len(doc),
            "character_count": character_count,
            "is_probably_scanned": is_probably_scanned,
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "text": "",
            "page_count": 0,
            "character_count": 0,
            "is_probably_scanned": False,
            "error": str(e)
        }