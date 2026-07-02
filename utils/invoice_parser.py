import re
from typing import Dict, Any, Optional


def clean_amount(value: Optional[str]) -> Optional[float]:
    """
    Convert amount strings like 'INR 124,000' or '124000' to float.
    """

    if not value:
        return None

    cleaned = value.upper()
    cleaned = cleaned.replace("INR", "")
    cleaned = cleaned.replace("USD", "")
    cleaned = cleaned.replace("₹", "")
    cleaned = cleaned.replace(",", "")
    cleaned = cleaned.strip()

    match = re.search(r"\d+(\.\d+)?", cleaned)

    if not match:
        return None

    return float(match.group())


def find_first(patterns: list[str], text: str) -> Optional[str]:
    """
    Try multiple regex patterns and return the first match.
    """

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()

    return None


def extract_description(text: str) -> str:
    """
    Extract meaningful invoice description from invoice text.
    This helps later when PO number is missing and we need to infer a PO.
    """

    description_parts = []

    description_patterns = [
        r"Description\s*:\s*(.+)",
        r"Project\s*:\s*(.+)",
        r"Note\s*:\s*(.+)"
    ]

    for pattern in description_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        description_parts.extend(matches)

    # Also capture line item area roughly
    line_item_match = re.search(
        r"Line Items\s*:\s*(.*?)(Subtotal|Tax|Total Amount Due|Total)",
        text,
        re.IGNORECASE | re.DOTALL
    )

    if line_item_match:
        line_items = line_item_match.group(1)
        line_items = re.sub(r"\s+", " ", line_items).strip()
        description_parts.append(line_items)

    return " | ".join([part.strip() for part in description_parts if part.strip()])


def calculate_parse_confidence(parsed: Dict[str, Any]) -> float:
    """
    Simple confidence score based on how many critical fields were found.
    """

    important_fields = [
        "invoice_number",
        "invoice_date",
        "vendor_name",
        "total_amount",
        "currency"
    ]

    found = 0

    for field in important_fields:
        if parsed.get(field) not in [None, "", 0]:
            found += 1

    return round(found / len(important_fields), 2)


def parse_invoice_text(text: str) -> Dict[str, Any]:
    """
    Parse raw invoice text into structured invoice fields.
    """

    invoice_number = find_first(
        [
            r"Invoice Number\s*:\s*([A-Z0-9\-\/]+)",
            r"Invoice No\.?\s*:\s*([A-Z0-9\-\/]+)",
            r"Invoice #\s*:\s*([A-Z0-9\-\/]+)"
        ],
        text
    )

    invoice_date = find_first(
        [
            r"Invoice Date\s*:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})",
            r"Date\s*:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})",
            r"Invoice Date\s*:\s*([0-9]{2}/[0-9]{2}/[0-9]{4})"
        ],
        text
    )

    vendor_name = find_first(
        [
            r"Vendor Name\s*:\s*(.+)",
            r"Vendor\s*:\s*(.+)"
        ],
        text
    )

    po_number = find_first(
        [
            r"PO Number\s*:\s*(PO-[0-9]+)",
            r"Purchase Order\s*:\s*(PO-[0-9]+)",
            r"PO\s*#\s*:\s*(PO-[0-9]+)"
        ],
        text
    )

    currency = find_first(
        [
            r"Currency\s*:\s*([A-Z]{3})",
            r"Total Amount Due\s*:\s*([A-Z]{3})",
            r"Subtotal\s*:\s*([A-Z]{3})"
        ],
        text
    )

    subtotal_raw = find_first(
        [
            r"Subtotal\s*:\s*(?:INR|USD|₹)?\s*([0-9,]+(?:\.\d+)?)"
        ],
        text
    )

    tax_raw = find_first(
        [
            r"Tax\s*:\s*(?:INR|USD|₹)?\s*([0-9,]+(?:\.\d+)?)"
        ],
        text
    )

    total_raw = find_first(
        [
            r"Total Amount Due\s*:\s*(?:INR|USD|₹)?\s*([0-9,]+(?:\.\d+)?)",
            r"Total\s*:\s*(?:INR|USD|₹)?\s*([0-9,]+(?:\.\d+)?)",
            r"Amount Due\s*:\s*(?:INR|USD|₹)?\s*([0-9,]+(?:\.\d+)?)"
        ],
        text
    )

    parsed = {
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "vendor_name": vendor_name,
        "po_number": po_number,
        "currency": currency or "INR",
        "subtotal": clean_amount(subtotal_raw),
        "tax": clean_amount(tax_raw),
        "total_amount": clean_amount(total_raw),
        "description": extract_description(text)
    }

    parsed["parse_confidence"] = calculate_parse_confidence(parsed)

    missing_fields = []

    required_fields = [
        "invoice_number",
        "invoice_date",
        "vendor_name",
        "total_amount"
    ]

    for field in required_fields:
        if parsed.get(field) in [None, ""]:
            missing_fields.append(field)

    parsed["missing_fields"] = missing_fields

    return parsed