import fitz
from pathlib import Path


OUTPUT_DIR = Path("sample_invoices")
OUTPUT_DIR.mkdir(exist_ok=True)


def create_invoice_pdf(filename: str, lines: list[str]):
    """
    Create a simple text-based invoice PDF using PyMuPDF.
    This keeps the project free and avoids extra PDF libraries.
    """

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    y = 60

    # Title
    page.insert_text(
        (50, y),
        "VENDOR INVOICE",
        fontsize=20,
        fontname="helv"
    )

    y += 40

    for line in lines:
        page.insert_text(
            (50, y),
            line,
            fontsize=11,
            fontname="helv"
        )
        y += 24

    output_path = OUTPUT_DIR / filename
    doc.save(output_path)
    doc.close()

    print(f"Created: {output_path}")


# 1. HAPPY PATH
# Approved vendor, clear PO, amount within tolerance.
create_invoice_pdf(
    "happy_path_clean_invoice.pdf",
    [
        "Invoice Number: INV-NT-2026-001",
        "Invoice Date: 2026-07-01",
        "Vendor Name: Northstar Tech Systems",
        "PO Number: PO-1002",
        "Currency: INR",
        "",
        "Line Items:",
        "Laptop docking stations - INR 90,000",
        "USB-C accessories - INR 25,000",
        "Service and handling - INR 9,000",
        "",
        "Subtotal: INR 124,000",
        "Tax: INR 0",
        "Total Amount Due: INR 124,000",
        "",
        "Payment Terms: Net 30",
        "Bank Account: XXXX-2211"
    ]
)


# 2. EDGE CASE: Missing PO but inferable
# Vendor is approved and amount/description strongly match PO-1004,
# but invoice does not mention a PO number.
create_invoice_pdf(
    "edge_1_missing_po_infer_candidate.pdf",
    [
        "Invoice Number: INV-VC-2026-018",
        "Invoice Date: 2026-07-01",
        "Vendor Name: Vertex Consulting",
        "Currency: INR",
        "",
        "Project: Automation process consulting",
        "Description: Consulting services for automation project",
        "",
        "Subtotal: INR 198,000",
        "Tax: INR 0",
        "Total Amount Due: INR 198,000",
        "",
        "Payment Terms: Net 15",
        "Note: PO reference not included by vendor."
    ]
)


# 3. EDGE CASE: Split PO / partial invoice
# PO-1003 has 80,000 total and already has 40,000 invoiced.
# This invoice is 39,500, so it fits within remaining balance.
create_invoice_pdf(
    "edge_2_split_po_partial_invoice.pdf",
    [
        "Invoice Number: INV-BP-2026-002",
        "Invoice Date: 2026-07-01",
        "Vendor Name: BluePeak Logistics",
        "PO Number: PO-1003",
        "Currency: INR",
        "",
        "Line Items:",
        "Freight services - second batch - INR 35,000",
        "Fuel surcharge - INR 4,500",
        "",
        "Subtotal: INR 39,500",
        "Tax: INR 0",
        "Total Amount Due: INR 39,500",
        "",
        "Note: This is the second invoice raised against the same PO."
    ]
)


# 4. EDGE CASE: Duplicate invoice
# This exact invoice already exists in processed_invoices.csv.
create_invoice_pdf(
    "edge_3_duplicate_invoice.pdf",
    [
        "Invoice Number: INV-DUP-001",
        "Invoice Date: 2026-07-01",
        "Vendor Name: Acme Office Supplies",
        "PO Number: PO-1001",
        "Currency: INR",
        "",
        "Line Items:",
        "Office chairs - INR 25,000",
        "",
        "Subtotal: INR 25,000",
        "Tax: INR 0",
        "Total Amount Due: INR 25,000",
        "",
        "Payment Terms: Net 30"
    ]
)


# 5. EDGE CASE: Amount above tolerance
# PO-1001 is 50,000 with 5% tolerance.
# Max allowed = 52,500.
# Invoice total is 58,000, so it should go to review.
create_invoice_pdf(
    "edge_4_amount_over_tolerance.pdf",
    [
        "Invoice Number: INV-ACME-2026-099",
        "Invoice Date: 2026-07-01",
        "Vendor Name: Acme Office Supplies",
        "PO Number: PO-1001",
        "Currency: INR",
        "",
        "Line Items:",
        "Office chairs and desks - INR 58,000",
        "",
        "Subtotal: INR 58,000",
        "Tax: INR 0",
        "Total Amount Due: INR 58,000",
        "",
        "Note: Final amount includes urgent delivery and packaging charges."
    ]
)